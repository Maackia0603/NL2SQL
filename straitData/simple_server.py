#!/usr/bin/env python3
"""
简化的 StraitData API 服务
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
import logging
from database import StraitDataDB

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 数据库连接配置
DB_CONNECTION_STRING = "postgresql+psycopg2://postgres:18343931600@localhost:5432/postgres"

# 创建 FastAPI 应用
app = FastAPI(title="StraitData API", version="1.0.0")

# CORS 设置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class StraitDataRequest(BaseModel):
    """海峡数据请求模型"""
    name: str = Field(..., alias="名称", description="名称")
    x: float = Field(..., alias="经度", description="经度")
    y: float = Field(..., alias="纬度", description="纬度")
    rect_length: float = Field(..., alias="矩形长", description="矩形长")
    rect_width: float = Field(..., alias="矩形宽", description="矩形宽")
    rotation: float = Field(..., alias="旋转角度参数", description="旋转角度参数")

    model_config = {
        "validate_by_name": True,
        "populate_by_name": True
    }

class StraitDataStoreRequest(BaseModel):
    """海峡数据存储请求模型"""
    name: str = Field(..., alias="名称", description="海峡名称")
    x: float = Field(..., alias="经度", description="中心点经度")
    y: float = Field(..., alias="纬度", description="中心点纬度")
    rect_length: float = Field(..., alias="矩形长", description="矩形长度（米）")
    rect_width: float = Field(..., alias="矩形宽", description="矩形宽度（米）")
    rotation: float = Field(..., alias="旋转角度参数", description="旋转角度（度）")
    description: str = Field(default="", alias="描述", description="海峡描述信息")
    category: str = Field(default="一般", alias="类别", description="海峡类别")
    
    model_config = {
        "validate_by_name": True,
        "populate_by_name": True
    }

@app.get("/")
async def root():
    return {"message": "StraitData API 服务运行中", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "straitData"}

@app.post("/straitData")
async def strait_data(req: StraitDataRequest):
    """海峡数据接口"""
    logger.info(f"📥 收到海峡数据请求: {req.model_dump(by_alias=True)}")
    
    try:
        # 创建数据库连接
        db = StraitDataDB(DB_CONNECTION_STRING)
        
        # 执行查询
        result = db.execute_strait_query(
            cx=req.x,  # 经度
            cy=req.y,  # 纬度
            length_x=req.rect_length,  # 矩形长
            length_y=req.rect_width,   # 矩形宽
            angle=req.rotation         # 旋转角度
        )
        
        # 关闭数据库连接
        db.close()
        
        if result["success"]:
            logger.info("✅ 海峡数据查询成功")
            return {
                "success": True,
                "message": "查询成功",
                "name": req.name,
                "parameters": {
                    "center": {"x": req.x, "y": req.y},
                    "rectangle": {"length": req.rect_length, "width": req.rect_width},
                    "rotation": req.rotation
                },
                "geojson": result["data"]
            }
        else:
            logger.error(f"❌ 查询失败: {result['message']}")
            raise HTTPException(status_code=500, detail=result["message"])
            
    except Exception as e:
        logger.error(f"❌ 处理请求时出错: {e}")
        raise HTTPException(status_code=500, detail=f"处理请求失败: {str(e)}")

@app.post("/storeStraitData")
async def store_strait_data(req: StraitDataStoreRequest):
    """存储海峡数据接口"""
    logger.info(f"📥 收到存储海峡数据请求: {req.model_dump(by_alias=True)}")
    
    try:
        logger.info(f"📝 开始存储海峡数据: {req.name}")
        logger.info(f"📍 位置信息: 经度={req.x}, 纬度={req.y}")
        logger.info(f"📐 几何信息: 长={req.rect_length}m, 宽={req.rect_width}m, 旋转={req.rotation}°")
        logger.info(f"📋 附加信息: 类别={req.category}, 描述={req.description}")
        
        # 创建数据库连接
        db = StraitDataDB(DB_CONNECTION_STRING)
        
        # 执行存储操作
        result = db.store_strait_data(
            name=req.name,
            cx=req.x,  # 经度
            cy=req.y,  # 纬度
            length_x=req.rect_length,  # 矩形长
            length_y=req.rect_width,   # 矩形宽
            angle=req.rotation         # 旋转角度
        )
        
        # 关闭数据库连接
        db.close()
        
        if result["success"]:
            logger.info("✅ 海峡数据存储成功")
            return {
                "success": True,
                "message": "海峡数据存储成功",
                "action": "存储海峡数据",
                "stored_data": {
                    "名称": req.name,
                    "经度": req.x,
                    "纬度": req.y,
                    "矩形长": req.rect_length,
                    "矩形宽": req.rect_width,
                    "旋转角度参数": req.rotation,
                    "描述": req.description,
                    "类别": req.category
                },
                "database_result": {
                    "affected_rows": result.get("affected_rows", 0),
                    "strait_name": result.get("strait_name", req.name)
                },
                "status": "数据已成功存储到数据库"
            }
        else:
            logger.error(f"❌ 存储失败: {result['message']}")
            raise HTTPException(status_code=500, detail=result["message"])
        
    except Exception as e:
        logger.error(f"❌ 处理存储请求时出错: {e}")
        raise HTTPException(status_code=500, detail=f"处理存储请求失败: {str(e)}")

if __name__ == "__main__":
    print("🌟 启动 StraitData API 服务器...")
    print("📍 服务地址: http://127.0.0.1:9001")
    print("📖 API文档: http://127.0.0.1:9001/docs")
    
    uvicorn.run(app, host="127.0.0.1", port=9001, log_level="info")
