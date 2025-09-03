from langchain_community.utilities import SQLDatabase
from mcp.server import FastMCP

# from sql_graph.my_llm import zhipuai_client
# from sql_graph.my_state import SQLState

mcp_server = FastMCP(name='lx-mcp', instructions='我自己的MCP服务', port=8000)

# db = SQLDatabase.from_uri('postgresql+psycopg2://readonly_user:Z+Idv6Nc^9%5k8]W0F;ghCa7M=41jxYA@localhost:15432/postgres')
# db = SQLDatabase.from_uri('postgresql+psycopg2://postgres:aisProjectData2025#!@localhost:15432/postgres')
# db = SQLDatabase.from_uri('postgresql+psycopg2://postgres:18343931600@localhost:5433/chinook')
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



# 存放所有来自mcp的工具，可以自定义根据业务需求

# @mcp_server.tool('get_schema_tool', description='Input to this tool is a comma-separated list of tables, output is the schema and sample rows for those tables. Be sure that the tables actually exist by calling sql_db_list_tables first! Example Input: table1, table2, table3')
# def get_schema_tool(state: SQLState):
#     return

@mcp_server.tool('add', description='加法运算，计算两个数字相加')
def add(a:int, b:int) -> int:
    return a + b


@mcp_server.tool('list_tables_tool', description='输入是一个空字符串, 返回数据库中的所有以逗号分隔的表名字列表')
def list_tables_tool() -> str:
    """输入是一个空字符串, 返回数据库中的所有以逗号分隔的表名字列表"""
    return ", ".join(db.get_usable_table_names())  #   ['emp': “这是一个员工表，”, '']


@mcp_server.tool('db_query_tool', description='执行SQL查询并返回结果。如果查询不正确，将返回错误信息。如果返回错误，请重写查询语句，检查后重试。')
def db_query_tool(query: str) -> str:
    """
    执行SQL查询并返回结果。
    如果查询不正确，将返回错误信息。
    如果返回错误，请重写查询语句，检查后重试。

    Args:
        query (str): 要执行的SQL查询语句

    Returns:
        str: 查询结果或错误信息
    """
    result = db.run_no_throw(query)  # 执行查询（不抛出异常）
    if not result:
        return "错误: 查询失败。请修改查询语句后重试。"
    return result