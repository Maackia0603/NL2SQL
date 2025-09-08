from contextlib import asynccontextmanager
from typing import Literal

from langchain_core.messages import AIMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.constants import START, END
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode, create_react_agent

from sql_graph.my_llm import llm
from sql_graph.my_state import SQLState
from sql_graph.tools_node import generate_query_system_prompt, query_check_system, call_get_schema, get_schema_node

# 用于与mcp客户端通信
mcp_server_config = {
    "url": "http://localhost:8000/sse",
    "transport": "sse" # SSE(服务端推送)是一种单向的服务器到客户端的通信方式，常用于推送实时流数据（比如模型流式输出 token）
}


def should_continue(state: SQLState) -> Literal[END, "check_query"]:
    """条件路由的，动态边"""
    messages = state["messages"]
    last_message = messages[-1]
    if not last_message.tool_calls:
        return END
    else:
        return "check_query"


# 作用：用于快速创建异步上下文管理器。它使得异步资源的获取和释放可以像同步代码一样通过 async with 语法优雅地管理。
@asynccontextmanager
async def make_graph():
    # 生成一个智能体
    client = MultiServerMCPClient({'data_mcp': mcp_server_config})
    # 可以连接多个mcp服务
    # client = MultiServerMCPClient({'lx_mcp': mcp_server_config, 'aliyun': sdf})
    # 拿mcp服务器资源
    # resourse = await client.get_resources('data_mcp', uri:mcp服务端资源数据)

    # 创建工作流
    """初始化MCPClient和工具，并且编译工作流"""
    # 与mcp客户端通信,因为mcp服务器是异步的，所以代码都是存放在异步中
    async with client.session('data_mcp') as session:

        # 拿到mcp的工具，工具需要智能体来调用
        tools = await load_mcp_tools(session)

        # 所有表名列表的工具 用于获取数据库中有哪些表
        list_tables_tool = next(tool for tool in tools if tool.name == "list_tables_tool")
        
        # 执行sql的工具
        db_query_tool = next(tool for tool in tools if tool.name == "db_query_tool")

        def call_list_tables(state: SQLState):
            """第一个节点 告诉模型去调用一个工具 构造一个 tool_call的请求指令"""
            tool_call = {
                "name": "list_tables_tool",
                "args": {}, # 传参
                "id": "abc123",
                "type": "tool_call",
            }
            # 指令包装为AIMessage
            tool_call_message = AIMessage(content="", tool_calls=[tool_call])

            # tool_message = list_tables_tool.invoke(tool_call)  # 调用工具
            #
            # response = AIMessage(f"所有可用的表: {tool_message.content}")
            #
            # return {"messages": [tool_call_message, tool_message, response]}
            return {"messages": [tool_call_message]}


        # 第二个节点 开始调用工具：ToolNode直接调用
        list_tables_tool = ToolNode([list_tables_tool], name="list_tables_tool")

        def generate_query(state: SQLState):
            """第五个节点: 生成SQL语句"""
            system_message = {
                "role": "system",
                "content": generate_query_system_prompt,
            }
            # 这里不强制工具调用，允许模型在获得解决方案时自然响应,不加tool_choice，自主决定调用工具，=any时必须选择工具调用
            llm_with_tools = llm.bind_tools([db_query_tool])
            # 提示词：[system_message];上下文：state['messages']
            resp = llm_with_tools.invoke([system_message] + state['messages'])
            return {'messages': [resp]}

        def check_query(state: SQLState):
            """第六个节点: 检查SQL语句。兼容缺少 tool_call.args.query 的情况，避免 KeyError。"""
            system_message = {
                "role": "system",
                "content": query_check_system,
            }
            last_msg = state["messages"][-1]
            proposed_query = None

            # 优先从工具调用里拿 query
            try:
                if getattr(last_msg, "tool_calls", None):
                    tc = last_msg.tool_calls[0]
                    args = tc.get("args") if isinstance(tc, dict) else None
                    if isinstance(args, dict):
                        proposed_query = args.get("query")
            except Exception:
                proposed_query = None

            # 回退：从消息文本中提取（若模型把 SQL 放在 content）
            if not proposed_query:
                content = getattr(last_msg, "content", "")
                if isinstance(content, str) and content.strip():
                    proposed_query = content.strip()

            # 仍无可用 SQL，则提示并退出本轮
            if not proposed_query:
                return {"messages": [AIMessage(content="未生成可检查的 SQL，请继续思考并给出查询语句。")]}

            user_message = {"role": "user", "content": proposed_query}
            llm_with_tools = llm.bind_tools([db_query_tool], tool_choice='any')
            response = llm_with_tools.invoke([system_message, user_message])
            response.id = last_msg.id

            return {"messages": [response]}

        # 第七个节点
        run_query_node = ToolNode([db_query_tool], name="run_query")

        # 创建工作流，得到工作流编译器
        workflow = StateGraph(SQLState)


        workflow.add_node(call_list_tables)
        workflow.add_node(list_tables_tool)
        workflow.add_node(call_get_schema)
        workflow.add_node(get_schema_node)
        workflow.add_node(generate_query)
        workflow.add_node(check_query)
        workflow.add_node(run_query_node)

        workflow.add_edge(START, "call_list_tables")
        workflow.add_edge("call_list_tables", "list_tables_tool")
        workflow.add_edge("list_tables_tool", "call_get_schema")
        workflow.add_edge("call_get_schema", "get_schema")
        workflow.add_edge("get_schema", "generate_query")
        workflow.add_conditional_edges('generate_query', should_continue)
        workflow.add_edge("check_query", "run_query")
        workflow.add_edge("run_query", "generate_query")

        graph = workflow.compile()
        yield graph # 异步通过yield返回
