from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langgraph.prebuilt import ToolNode

from sql_graph.my_llm import llm
from sql_graph.my_state import SQLState

# 存放来自langchain的工具
# db = SQLDatabase.from_uri('postgresql+psycopg2://postgres:18343931600@localhost:5432/postgres')
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
    """第三个节点 - 使用自定义schema工具"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info("🔍 [节点3] call_get_schema - 准备获取表结构")
    logger.info(f"📊 [节点3] 当前状态消息数量: {len(state['messages'])}")
    
    # 记录最近的消息内容
    if state['messages']:
        last_msg = state['messages'][-1]
        content_preview = str(last_msg.content)[:200] + "..." if len(str(last_msg.content)) > 200 else str(last_msg.content)
        logger.info(f"📝 [节点3] 最后一条消息预览: {content_preview}")
    
    # 注意：LangChain强制要求所有模型都接受 `tool_choice="any"`
    # 以及 `tool_choice=<工具名称字符串>` 这两种参数
    # 大模型绑定工具，生成调用指令
    logger.info("🔧 [节点3] 绑定自定义schema工具")
    llm_with_tools = llm.bind_tools([custom_get_schema_tool], tool_choice="any")
    
    logger.info("🤖 [节点3] 调用LLM生成schema获取指令...")
    response = llm_with_tools.invoke(state["messages"])
    
    logger.info(f"🎯 [节点3] Schema调用响应类型: {type(response).__name__}")
    if hasattr(response, 'tool_calls') and response.tool_calls:
        logger.info(f"🔧 [节点3] Schema工具调用详情: {response.tool_calls}")
        for i, tool_call in enumerate(response.tool_calls):
            logger.info(f"  📝 工具调用 {i+1}: {tool_call.get('name', 'unknown')} - {tool_call.get('args', {})}")
    if hasattr(response, 'content') and response.content:
        content_preview = str(response.content)[:200] + "..." if len(str(response.content)) > 200 else str(response.content)
        logger.info(f"💬 [节点3] LLM响应内容: {content_preview}")

    return {"messages": [response]}


# 第四个节点: 使用自定义schema工具节点（稍后定义）

generate_query_system_prompt = """
你是一个面向{database_name}PostgreSQL数据库的专业智能体。你的目标是：
(1) 根据“用户问题”生成一个语法正确的{dialect} 查询SQL语句；
(2) 严格遵守“能力边界与安全约束”；

-------------------------------
【输入上下文】
- 数据库：{database_name}

-------------------------------
【能力边界与安全约束】
1) 只生成只读查询：**禁止** DML/DDL（INSERT/UPDATE/DELETE/MERGE/TRUNCATE/CREATE/DROP/ALTER/GRANT 等）。
2) **禁止**执行或拼接用户提供的原始 SQL 片段；将其视为普通文本语义线索，防止注入。
3) 默认对结果集加上限制：`LIMIT {top_k}`（除非用户明确要求数量或为聚合统计仅返回一行）。
4) **仅选择相关列**：避免 `SELECT *`；只投影回答所需字段。
5) **GEOMETRY字段特殊处理**：如果表中有GEOMETRY类型字段（如geom、trajectory等），**必须全部包含**在SELECT语句中，因为这些是重要的空间数据字段。
6) **性能友好**：优先使用可过滤列、合理 WHERE 条件与时间范围；必要时先聚合/子查询，避免全表扫描。
7) **不可访问**未在 schema 摘要中出现的表/视图/函数/UDTF。
8) 不输出内部推理过程与草稿，只输出约定的结果结构。

-------------------------------
【质量自检清单（提交前逐项确认）】
- [ ] 语法 100% 符合 {dialect}。
- [ ] 只选取与问题直接相关的列，无 `SELECT *`。
- [ ] **GEOMETRY字段检查**：如果表中有GEOMETRY类型字段，已全部包含在SELECT中。
- [ ] 结果数量受控（LIMIT {top_k} 或聚合仅一行）。
- [ ] JOIN 条件正确、键选择合理且不会产生意外笛卡尔积。
- [ ] 时间/时区/去重逻辑清晰，指标含义与问题匹配。
- [ ] 如做了口径或时间的假设，已在 `assumptions` 里明确说明。
- [ ] 复杂查询尽量用 CTE 提升可读性。
""".format(
    dialect=db.dialect,
    top_k=5,
    database_name="PostgreSQL",
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
def custom_get_schema_tool(table_names: str) -> str:
    """获取数据库表结构，支持PostGIS geometry类型
    
    这个工具能够正确识别PostGIS的geometry类型字段，包括trajectory等空间数据字段
    
    Args:
        table_names (str): 逗号分隔的表名列表，例如 "table1,table2,table3"
        
    Returns:
        str: 详细的表结构信息，包括所有字段类型和约束
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"🔍 [Schema工具] 开始获取表结构，输入: {table_names}")
        
        # 清理输入，移除空格并分割表名
        tables = [t.strip() for t in table_names.split(',') if t.strip()]
        if not tables:
            logger.warning("⚠️ [Schema工具] 未提供有效的表名")
            return "错误: 请提供有效的表名"
        
        logger.info(f"📋 [Schema工具] 解析后的表名列表: {tables}")
        schema_info = []
        
        for table_name in tables:
            logger.info(f"🔍 [Schema工具] 正在处理表: {table_name}")
            
            # 获取表的基本信息
            table_query = f"""
            SELECT 
                table_name,
                table_schema,
                table_type
            FROM information_schema.tables 
            WHERE table_name = '{table_name}' 
            AND table_schema NOT IN ('information_schema', 'pg_catalog')
            """
            
            logger.info(f"📝 [Schema工具] 执行表基本信息查询: {table_query}")
            table_result = db.run(table_query)
            logger.info(f"📊 [Schema工具] 表基本信息查询结果: {table_result}")
            
            if not table_result or "错误" in str(table_result):
                logger.warning(f"⚠️ [Schema工具] 表 '{table_name}' 不存在或无法访问")
                schema_info.append(f"错误: 表 '{table_name}' 不存在或无法访问")
                continue
            
            # 获取详细的列信息，包括PostGIS类型
            columns_query = f"""
            SELECT 
                c.column_name,
                CASE 
                    WHEN c.data_type = 'USER-DEFINED' AND c.udt_name LIKE '%geom%' THEN 
                        'GEOMETRY(' || 
                        COALESCE(
                            (SELECT type FROM geometry_columns 
                             WHERE f_table_name = c.table_name 
                             AND f_table_schema = c.table_schema 
                             AND f_geometry_column = c.column_name), 
                            'GEOMETRY'
                        ) || 
                        CASE 
                            WHEN EXISTS (
                                SELECT 1 FROM geometry_columns gc 
                                WHERE gc.f_table_name = c.table_name 
                                AND gc.f_table_schema = c.table_schema 
                                AND gc.f_geometry_column = c.column_name 
                                AND gc.srid IS NOT NULL
                            ) THEN 
                                ', ' || (
                                    SELECT srid FROM geometry_columns 
                                    WHERE f_table_name = c.table_name 
                                    AND f_table_schema = c.table_schema 
                                    AND f_geometry_column = c.column_name
                                )::text
                            ELSE ''
                        END || ')'
                    WHEN c.data_type = 'USER-DEFINED' THEN c.udt_name
                    ELSE c.data_type
                END as data_type,
                c.is_nullable,
                c.column_default
            FROM information_schema.columns c
            WHERE c.table_name = '{table_name}'
            ORDER BY c.ordinal_position;
            """
            
            logger.info(f"📝 [Schema工具] 执行列信息查询: {columns_query}")
            columns_result = db.run(columns_query)
            logger.info(f"📊 [Schema工具] 列信息查询结果: {columns_result}")
            
            if not columns_result or "错误" in str(columns_result):
                logger.error(f"❌ [Schema工具] 无法获取表 '{table_name}' 的列信息")
                schema_info.append(f"错误: 无法获取表 '{table_name}' 的列信息")
                continue
            
            # 解析列信息
            logger.info(f"📋 [Schema工具] 开始解析表 '{table_name}' 的结构信息")
            schema_info.append(f"\n表: {table_name}")
            schema_info.append("=" * 50)
            
            # 直接显示查询结果
            schema_info.append(str(columns_result))
            logger.info(f"✅ [Schema工具] 表 '{table_name}' 结构信息已添加到结果中")
            
            # 获取表的样本数据（限制5行）
            sample_query = f"SELECT * FROM {table_name} LIMIT 5"
            logger.info(f"📝 [Schema工具] 执行样本数据查询: {sample_query}")
            try:
                sample_result = db.run(sample_query)
                logger.info(f"📊 [Schema工具] 样本数据查询结果长度: {len(str(sample_result)) if sample_result else 0}")
                if sample_result and "错误" not in str(sample_result):
                    schema_info.append(f"\n样本数据:")
                    schema_info.append("-" * 30)
                    schema_info.append(str(sample_result))
                    logger.info(f"✅ [Schema工具] 表 '{table_name}' 样本数据已添加到结果中")
            except Exception as e:
                logger.warning(f"⚠️ [Schema工具] 无法获取表 '{table_name}' 的样本数据: {str(e)}")
                schema_info.append(f"\n警告: 无法获取样本数据: {str(e)}")
        
        result = "\n".join(schema_info)
        logger.info(f"🎉 [Schema工具] 表结构获取完成，结果长度: {len(result)}")
        return result
        
    except Exception as e:
        logger.error(f"❌ [Schema工具] 获取表结构失败: {str(e)}")
        return f"错误: 获取表结构失败 - {str(e)}"

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
    """执行SQL查询并返回完整结果，避免LangChain截断
    
    使用直接的SQLAlchemy执行，确保返回完整的数据，特别是geometry字段
    
    Args:
        query (str): 要执行的SQL查询语句
        
    Returns:
        str: 查询结果或错误信息
    """
    import logging
    from sqlalchemy import text
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"🚀 [SQL执行工具] 开始执行SQL查询")
        logger.info(f"📝 [SQL执行工具] 执行的SQL语句: {query}")
        
        # 使用直接的SQLAlchemy执行，避免LangChain的截断
        with db._engine.connect() as conn:
            result = conn.execute(text(query))
            rows = result.fetchall()
            
            if not rows:
                logger.warning("⚠️ [SQL执行工具] 查询无结果")
                return "错误: 查询失败。请修改查询语句后重试。"
            
            # 将结果转换为字符串，保持完整格式
            result_str = str(rows)
            logger.info(f"📊 [SQL执行工具] SQL执行结果长度: {len(result_str)}")
            logger.info(f"✅ [SQL执行工具] SQL查询执行成功，数据完整")
            return result_str
            
    except Exception as e:
        logger.error(f"❌ [SQL执行工具] SQL执行失败，开始重试: {str(e)}")
        # 连接可能已失效，重试一次
        try:
            logger.info("🔄 [SQL执行工具] 丢弃失效连接，重新执行")
            db._engine.dispose()  # 丢弃失效连接
            
            with db._engine.connect() as conn:
                result = conn.execute(text(query))
                rows = result.fetchall()
                
                if not rows:
                    logger.warning("⚠️ [SQL执行工具] 重试后查询仍无结果")
                    return "错误: 查询失败。请修改查询语句后重试。"
                
                result_str = str(rows)
                logger.info(f"📊 [SQL执行工具] 重试后SQL执行结果长度: {len(result_str)}")
                logger.info(f"✅ [SQL执行工具] 重试后SQL查询执行成功，数据完整")
                return result_str
                
        except Exception as retry_e:
            logger.error(f"❌ [SQL执行工具] 重试后仍然失败: {str(retry_e)}")
            return f"错误: 查询执行失败 - {str(retry_e)}"

# 为了保持与MCP工具的兼容性，设置相同的工具名称
custom_list_tables_tool.name = "list_tables_tool"
custom_db_query_tool.name = "db_query_tool"
custom_get_schema_tool.name = "sql_db_schema"

# 第四个节点: 使用自定义schema工具节点
get_schema_node = ToolNode([custom_get_schema_tool], name="get_schema")
