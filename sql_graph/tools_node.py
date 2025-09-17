from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langgraph.prebuilt import ToolNode

from sql_graph.my_llm import llm
from sql_graph.my_state import SQLState

# 存放来自langchain的工具
# db = SQLDatabase.from_uri('postgresql+psycopg2://postgres:18343931600@localhost:5433/chinook')
# db = SQLDatabase.from_uri('postgresql+psycopg2://readonly_user:Z+Idv6Nc^9%5k8]W0F;ghCa7M=41jxYA@localhost:15432/postgres')
db = SQLDatabase.from_uri(
    'postgresql+psycopg2://readonly_user:Z+Idv6Nc^9%5k8]W0F;ghCa7M=41jxYA@localhost:15432/postgres',
    engine_args={
        "pool_pre_ping": True,          # 每次借用连接前发心跳，自动剔除坏连接
        "pool_recycle": 1800,           # 连接存活时间（秒），定期回收
        "pool_size": 5,                 # 连接池大小
        "max_overflow": 10,             # 允许的溢出连接
        "connect_args": {               # 客户端 TCP keepalive
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        },
    },
)

toolkit = SQLDatabaseToolkit(db=db, llm=llm)

tools = toolkit.get_tools()

# 获取表结构的工具
get_schema_tool = next(tool for tool in tools if tool.name == 'sql_db_schema')

# 获取数据库查询工具
db_query_tool = next(tool for tool in tools if tool.name == 'sql_db_query')

# 测试工具调用
# print(get_schema_tool.invoke('employees'))
# print(db_query_tool.invoke('SELECT * FROM employees LIMIT 5'))

# 同步的工具代码

def call_get_schema(state: SQLState):
    """ 第三个节点"""
    # 注意：LangChain强制要求所有模型都接受 `tool_choice="any"`
    # 以及 `tool_choice=<工具名称字符串>` 这两种参数
    # 大模型绑定工具，生成调用指令
    llm_with_tools = llm.bind_tools([get_schema_tool], tool_choice="any")
    response = llm_with_tools.invoke(state["messages"])

    return {"messages": [response]}


# 第四个节点: 直接使用langgraph提供的ToolNode[直接使用工具]
get_schema_node = ToolNode([get_schema_tool], name="get_schema")

generate_query_system_prompt = """
你是一个设计用于与SQL数据库交互的智能体。
给定一个输入问题，创建一个语法正确的{dialect}查询来运行，
然后查看查询结果并返回答案。除非用户明确指定他们希望获取的示例数量，
否则始终将查询限制为最多{top_k}个结果。

你可以按相关列对结果进行排序，以返回数据库中最有趣的示例。
永远不要查询特定表的所有列，只询问与问题相关的列。

不要对数据库执行任何DML语句（INSERT、UPDATE、DELETE、DROP等）。
""".format(
    dialect=db.dialect,
    top_k=5,
)


query_check_system = """您是一位注重细节的SQL专家。
请仔细检查SQL查询中的常见错误，包括：
- Using NOT IN with NULL values
- Using UNION when UNION ALL should have been used
- Using BETWEEN for exclusive ranges
- Data type mismatch in predicates
- Properly quoting identifiers
- Using the correct number of arguments for functions
- Casting to the correct data type
- Using the proper columns for joins

如果发现上述任何错误，请重写查询。如果没有错误，请原样返回查询语句。

检查完成后，您将调用适当的工具来执行查询。"""

# ===== 自定义本地工具 (当前使用，替代MCP工具) =====
"""
这些工具提供与MCP工具相同的功能，但直接在本地执行，无需外部服务。
与mcp_server/mcp_tools.py中的工具功能完全一致。

优势：
- 无需启动MCP服务器
- 减少网络通信开销
- 简化部署和调试
- 提高响应速度
"""

from langchain_core.tools import tool

@tool
def custom_list_tables_tool() -> str:
    """获取数据库中所有表的列表
    
    这个工具与 mcp_server/mcp_tools.py 中的 list_tables_tool 功能完全一致
    
    Returns:
        str: 以逗号分隔的表名列表
    """
    try:
        table_names = db.get_usable_table_names()
        return ", ".join(table_names)
    except Exception as e:
        return f"错误: 获取表列表失败 - {str(e)}"

@tool  
def custom_db_query_tool(query: str) -> str:
    """执行SQL查询并返回结果
    
    这个工具与 mcp_server/mcp_tools.py 中的 db_query_tool 功能完全一致
    包含相同的错误处理和重试机制
    
    Args:
        query (str): 要执行的SQL查询语句
        
    Returns:
        str: 查询结果或错误信息
    """
    try:
        result = db.run_no_throw(query)
        if not result:
            return "错误: 查询失败。请修改查询语句后重试。"
        return result
    except Exception as e:
        # 连接可能已失效，重试一次 (与MCP版本相同的重试逻辑)
        try:
            if hasattr(db, 'engine'):
                db.engine.dispose()  # 丢弃失效连接
            result = db.run_no_throw(query)
            if not result:
                return "错误: 查询失败。请修改查询语句后重试。"
            return result
        except Exception as retry_e:
            return f"错误: 查询执行失败 - {str(retry_e)}"

# 为了保持与MCP工具的兼容性，设置相同的工具名称
custom_list_tables_tool.name = "list_tables_tool"
custom_db_query_tool.name = "db_query_tool"
