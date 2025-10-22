from contextlib import asynccontextmanager
from typing import Any, Dict, List
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from sql_graph.text2sql_graph import make_graph

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('api_server.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class AskRequest(BaseModel):
    question: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 启动API服务器...")
    try:
        async with make_graph() as graph:
            app.state.graph = graph
            logger.info("✅ NL2SQL Agent图已加载")
            yield
    except Exception as e:
        logger.error(f"❌ 启动失败: {e}")
        raise
    finally:
        logger.info("🔚 API服务器关闭")


app = FastAPI(lifespan=lifespan)

# CORS 设置
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/ask")
async def ask(req: AskRequest) -> Dict[str, Any]:
    logger.info(f"📥 收到新的查询请求: {req.question}")
    outputs: List[str] = []
    sql_data = None  # 存储SQL执行结果
    
    try:
        # 增加递归限制，防止无限循环
        config = {"recursion_limit": 50}
        logger.info(f"⚙️ 使用配置: {config}")
        
        step_count = 0
        logger.info("🔄 开始执行工作流...")
        
        async for event in app.state.graph.astream(
            {"messages": [{"role": "user", "content": req.question}]},
            stream_mode="values",
            config=config,
        ):
            step_count += 1
            logger.info(f"📊 第{step_count}步执行完成")
            
            # 从状态中获取SQL数据（如果存在）
            if "sql_data" in event and event["sql_data"]:
                sql_data = event["sql_data"]
                logger.info(f"📊 从状态中获取SQL数据，数据长度: {len(str(sql_data))}")
                continue  # SQL数据不进入消息流，直接跳过
            
            msg = event["messages"][-1]
            content = getattr(msg, "content", None)
            
            # 记录消息详情
            logger.info(f"📝 消息类型: {type(msg).__name__}")
            if content:
                content_preview = str(content)[:200] + "..." if len(str(content)) > 200 else str(content)
                logger.info(f"💬 消息内容: {content_preview}")
            
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                logger.info(f"🔧 工具调用: {msg.tool_calls}")
                
            outputs.append(content if isinstance(content, str) else str(content))
        
        logger.info(f"✅ 工作流执行完成，总共{step_count}步，生成{len(outputs)}个输出")
        
        # 构建返回结果
        result = {
            # "outputs": outputs, 
            # "final": outputs[-1] if outputs else "",
            "data": sql_data  # 添加SQL执行结果作为data字段
        }
        
        if sql_data:
            logger.info(f"📤 返回结果包含SQL数据，数据长度: {len(str(sql_data))}")
        else:
            logger.info(f"📤 返回结果: final='{result['final'][:100]}...' (共{len(outputs)}个输出)")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ 处理请求时出错: {e}")
        error_result = {
            "outputs": [f"处理出错: {str(e)}"], 
            "final": f"处理出错: {str(e)}",
            "data": None
        }
        return error_result


if __name__ == "__main__":
    import uvicorn
    
    logger.info("🌟 启动NL2SQL API服务器...")
    logger.info("📍 服务地址: http://127.0.0.1:9000")
    logger.info("📖 API文档: http://127.0.0.1:9000/docs")
    
    uvicorn.run("api.api_server:app", host="127.0.0.1", port=9000, reload=True)


