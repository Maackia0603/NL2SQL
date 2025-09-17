from contextlib import asynccontextmanager
from typing import Literal
import logging

from langchain_core.messages import AIMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.constants import START, END
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode, create_react_agent

from sql_graph.my_llm import llm
from sql_graph.my_state import SQLState
from sql_graph.tools_node import generate_query_system_prompt, query_check_system, call_get_schema, get_schema_node

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('nl2sql_agent.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# 用于与mcp客户端通信
mcp_server_config = {
    "url": "http://localhost:8000/sse",
    "transport": "sse" # SSE(服务端推送)是一种单向的服务器到客户端的通信方式，常用于推送实时流数据（比如模型流式输出 token）
}


def should_continue(state: SQLState) -> Literal[END, "check_query"]:
    """条件路由的，动态边"""
    messages = state["messages"]
    last_message = messages[-1]
    
    logger.info(f"🔀 should_continue 检查 - 消息总数: {len(messages)}")
    logger.info(f"📝 最后消息类型: {type(last_message).__name__}")
    logger.info(f"🔧 是否有工具调用: {hasattr(last_message, 'tool_calls') and bool(last_message.tool_calls)}")
    
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        logger.info(f"🛠️ 工具调用详情: {last_message.tool_calls}")
    
    if hasattr(last_message, 'content') and last_message.content:
        content_preview = str(last_message.content)[:100] + "..." if len(str(last_message.content)) > 100 else str(last_message.content)
        logger.info(f"💬 消息内容预览: {content_preview}")
    
    if not last_message.tool_calls:
        logger.info("✅ 没有工具调用，工作流结束")
        return END
    else:
        logger.info("🔄 有工具调用，继续到check_query节点")
        return "check_query"


# 作用：用于快速创建异步上下文管理器。它使得异步资源的获取和释放可以像同步代码一样通过 async with 语法优雅地管理。
@asynccontextmanager
async def make_graph():
    logger.info("🚀 开始初始化NL2SQL Agent工作流")
    
    # 生成一个智能体
    logger.info("📡 连接MCP客户端...")
    client = MultiServerMCPClient({'data_mcp': mcp_server_config})
    # 可以连接多个mcp服务
    # client = MultiServerMCPClient({'lx_mcp': mcp_server_config, 'aliyun': sdf})
    # 拿mcp服务器资源
    # resourse = await client.get_resources('data_mcp', uri:mcp服务端资源数据)

    # 创建工作流
    """初始化MCPClient和工具，并且编译工作流"""
    # 与mcp客户端通信,因为mcp服务器是异步的，所以代码都是存放在异步中
    try:
        async with client.session('data_mcp') as session:
            logger.info("✅ MCP客户端连接成功")

            # 拿到mcp的工具，工具需要智能体来调用
            logger.info("🔧 加载MCP工具...")
            tools = await load_mcp_tools(session)
            logger.info(f"📦 成功加载 {len(tools)} 个工具: {[tool.name for tool in tools]}")

            # 所有表名列表的工具 用于获取数据库中有哪些表
            list_tables_tool = next(tool for tool in tools if tool.name == "list_tables_tool")
            logger.info(f"✅ 获取表列表工具: {list_tables_tool.name}")
            
            # 执行sql的工具
            db_query_tool = next(tool for tool in tools if tool.name == "db_query_tool")
            logger.info(f"✅ 获取数据库查询工具: {db_query_tool.name}")

            def call_list_tables(state: SQLState):
                """第一个节点 告诉模型去调用一个工具 构造一个 tool_call的请求指令"""
                logger.info("🗂️ [节点1] call_list_tables - 准备获取数据库表列表")
                logger.info(f"📊 当前状态消息数量: {len(state['messages'])}")
                
                tool_call = {
                    "name": "list_tables_tool",
                    "args": {}, # 传参
                    "id": "abc123",
                    "type": "tool_call",
                }
                # 指令包装为AIMessage
                tool_call_message = AIMessage(content="", tool_calls=[tool_call])
                logger.info(f"📤 生成工具调用指令: {tool_call}")

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
                logger.info("🧠 [节点5] generate_query - 开始生成SQL查询")
                logger.info(f"📊 当前状态消息数量: {len(state['messages'])}")
                
                # 记录最近的消息内容
                if state['messages']:
                    last_msg = state['messages'][-1]
                    content_preview = str(last_msg.content)[:200] + "..." if len(str(last_msg.content)) > 200 else str(last_msg.content)
                    logger.info(f"📝 最后一条消息预览: {content_preview}")
                
                system_message = {
                    "role": "system",
                    "content": generate_query_system_prompt,
                }
                # 这里不强制工具调用，允许模型在获得解决方案时自然响应,不加tool_choice，自主决定调用工具，=any时必须选择工具调用
                llm_with_tools = llm.bind_tools([db_query_tool])
                
                logger.info("🤖 调用LLM生成SQL查询...")
                # 提示词：[system_message];上下文：state['messages']
                resp = llm_with_tools.invoke([system_message] + state['messages'])
                
                # 记录LLM响应
                logger.info(f"🎯 LLM响应类型: {type(resp).__name__}")
                if hasattr(resp, 'content') and resp.content:
                    content_preview = str(resp.content)[:200] + "..." if len(str(resp.content)) > 200 else str(resp.content)
                    logger.info(f"💬 LLM响应内容: {content_preview}")
                if hasattr(resp, 'tool_calls') and resp.tool_calls:
                    logger.info(f"🔧 LLM生成的工具调用: {resp.tool_calls}")
                
                return {'messages': [resp]}

            def check_query(state: SQLState):
                """第六个节点: 检查SQL语句。兼容缺少 tool_call.args.query 的情况，避免 KeyError。"""
                logger.info("🔍 [节点6] check_query - 开始检查SQL语句")
                logger.info(f"📊 当前状态消息数量: {len(state['messages'])}")
                
                system_message = {
                    "role": "system",
                    "content": query_check_system,
                }
                last_msg = state["messages"][-1]
                proposed_query = None

                logger.info(f"🔎 分析最后一条消息: {type(last_msg).__name__}")

                # 优先从工具调用里拿 query
                try:
                    if getattr(last_msg, "tool_calls", None):
                        tc = last_msg.tool_calls[0]
                        logger.info(f"🛠️ 找到工具调用: {tc}")
                        args = tc.get("args") if isinstance(tc, dict) else None
                        if isinstance(args, dict):
                            proposed_query = args.get("query")
                            logger.info(f"📝 从工具调用提取SQL: {proposed_query}")
                except Exception as e:
                    logger.warning(f"⚠️ 从工具调用提取SQL失败: {e}")
                    proposed_query = None

                # 回退：从消息文本中提取（若模型把 SQL 放在 content）
                if not proposed_query:
                    content = getattr(last_msg, "content", "")
                    if isinstance(content, str) and content.strip():
                        proposed_query = content.strip()
                        logger.info(f"📝 从消息内容提取SQL: {proposed_query}")

                # 仍无可用 SQL，则提示并退出本轮
                if not proposed_query:
                    logger.error("❌ 未能提取到有效的SQL查询")
                    return {"messages": [AIMessage(content="未生成可检查的 SQL，请继续思考并给出查询语句。")]}

                logger.info(f"✅ 成功提取SQL查询: {proposed_query}")
                logger.info("🤖 调用LLM检查SQL查询...")
                
                user_message = {"role": "user", "content": proposed_query}
                llm_with_tools = llm.bind_tools([db_query_tool], tool_choice='any')
                response = llm_with_tools.invoke([system_message, user_message])
                response.id = last_msg.id

                logger.info(f"🎯 SQL检查响应: {type(response).__name__}")
                if hasattr(response, 'tool_calls') and response.tool_calls:
                    logger.info(f"🔧 检查后生成的工具调用: {response.tool_calls}")

                return {"messages": [response]}

            # 第七个节点
            run_query_node = ToolNode([db_query_tool], name="run_query")
            logger.info("✅ 创建SQL执行节点")

            # 创建工作流，得到工作流编译器
            logger.info("🏗️ 开始构建工作流...")
            workflow = StateGraph(SQLState)

            # 添加节点
            logger.info("➕ 添加工作流节点...")
            workflow.add_node(call_list_tables)
            workflow.add_node(list_tables_tool)
            workflow.add_node(call_get_schema)
            workflow.add_node(get_schema_node)
            workflow.add_node(generate_query)
            workflow.add_node(check_query)
            workflow.add_node(run_query_node)
            logger.info("✅ 所有节点添加完成")

            # 添加边
            logger.info("🔗 添加工作流边...")
            workflow.add_edge(START, "call_list_tables")
            workflow.add_edge("call_list_tables", "list_tables_tool")
            workflow.add_edge("list_tables_tool", "call_get_schema")
            workflow.add_edge("call_get_schema", "get_schema")
            workflow.add_edge("get_schema", "generate_query")
            workflow.add_conditional_edges('generate_query', should_continue)
            workflow.add_edge("check_query", "run_query")
            workflow.add_edge("run_query", "generate_query")
            logger.info("✅ 所有边添加完成")

            logger.info("🔧 编译工作流...")
            graph = workflow.compile()
            logger.info("🎉 NL2SQL Agent工作流初始化完成!")
            
            yield graph # 异步通过yield返回
            
    except Exception as e:
        logger.error(f"❌ 初始化工作流失败: {e}")
        raise
