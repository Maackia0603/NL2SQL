# StraitData API

海峡数据查询和存储API服务，提供基于PostGIS的海峡几何数据计算和存储功能。

## 功能特性

- 🔍 **海峡数据查询**: 根据参数计算海峡水域几何数据
- 💾 **海峡数据存储**: 将海峡数据存储到PostgreSQL数据库
- 🗺️ **空间计算**: 基于PostGIS的复杂几何计算
- 🌐 **RESTful API**: 标准的REST API接口
- 📖 **自动文档**: Swagger UI自动生成API文档
- 🔄 **中英文支持**: 支持中英文字段名

## 技术栈

- **FastAPI**: 现代、快速的Web框架
- **PostgreSQL + PostGIS**: 空间数据库
- **SQLAlchemy**: Python SQL工具包
- **Pydantic**: 数据验证和序列化

## 快速开始

### 1. 环境要求

- Python 3.8+
- PostgreSQL 12+ with PostGIS extension
- 已安装coastline表（海岸线数据）

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置数据库

修改 `simple_server.py` 中的数据库连接字符串：

```python
DB_CONNECTION_STRING = "postgresql+psycopg2://username:password@localhost:5432/database_name"
```

### 4. 启动服务

```bash
# 激活环境（如果使用conda）
conda activate NL2SQL

# 启动服务
python simple_server.py
```

**或者直接运行（如果环境已配置）：**
```bash
python simple_server.py
```

服务将在 `http://127.0.0.1:9001` 启动

## API 接口

### 基础接口

- **GET** `/` - API信息
- **GET** `/health` - 健康检查
- **GET** `/docs` - Swagger API文档

### 海峡数据查询

**POST** `/straitData`

查询海峡水域几何数据。

#### 请求参数

```json
{
  "名称": "台湾海峡",
  "经度": 119.5,
  "纬度": 24.0,
  "矩形长": 150000.0,
  "矩形宽": 200000.0,
  "旋转角度参数": 15.0
}
```

#### 响应

```json
{
  "success": true,
  "message": "查询成功",
  "name": "台湾海峡",
  "parameters": {
    "center": {"x": 119.5, "y": 24.0},
    "rectangle": {"length": 150000.0, "width": 200000.0},
    "rotation": 15.0
  },
  "geojson": {
    "type": "FeatureCollection",
    "features": [...]
  }
}
```

### 海峡数据存储

**POST** `/storeStraitData`

将海峡数据存储到数据库。

#### 请求参数

```json
{
  "名称": "马六甲海峡",
  "经度": 100.193875,
  "纬度": 3.39047865,
  "矩形长": 450000.0,
  "矩形宽": 900000.0,
  "旋转角度参数": 40.0,
  "描述": "连接印度洋和太平洋的重要国际航运通道",
  "类别": "国际重要海峡"
}
```

#### 响应

```json
{
  "success": true,
  "message": "海峡数据存储成功",
  "action": "存储海峡数据",
  "stored_data": {
    "名称": "马六甲海峡",
    "经度": 100.193875,
    "纬度": 3.39047865,
    "矩形长": 450000.0,
    "矩形宽": 900000.0,
    "旋转角度参数": 40.0,
    "描述": "连接印度洋和太平洋的重要国际航运通道",
    "类别": "国际重要海峡"
  },
  "database_result": {
    "affected_rows": 1,
    "strait_name": "马六甲海峡"
  },
  "status": "数据已成功存储到数据库"
}
```

## 测试示例

### 使用curl测试

```bash
# 查询海峡数据
curl -X POST "http://127.0.0.1:9001/straitData" \
  -H "Content-Type: application/json" \
  -d '{
    "名称": "台湾海峡",
    "经度": 119.5,
    "纬度": 24.0,
    "矩形长": 150000.0,
    "矩形宽": 200000.0,
    "旋转角度参数": 15.0
  }'

# 存储海峡数据
curl -X POST "http://127.0.0.1:9001/storeStraitData" \
  -H "Content-Type: application/json" \
  -d '{
    "名称": "马六甲海峡",
    "经度": 100.193875,
    "纬度": 3.39047865,
    "矩形长": 450000.0,
    "矩形宽": 900000.0,
    "旋转角度参数": 40.0,
    "描述": "连接印度洋和太平洋的重要国际航运通道",
    "类别": "国际重要海峡"
  }'
```

### 使用Postman测试

1. 导入API文档：访问 `http://127.0.0.1:9001/docs`
2. 使用Swagger UI进行交互式测试

## 数据库结构

### straits表

```sql
CREATE TABLE straits (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    x DOUBLE PRECISION NOT NULL,
    y DOUBLE PRECISION NOT NULL,
    geom GEOMETRY(POLYGON, 4326),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### coastline表（需要预先准备）

包含海岸线几何数据的表，用于海峡水域计算。

## 项目结构

```
straitData/
├── database.py          # 数据库操作模块
├── simple_server.py     # 主API服务器
├── requirements.txt     # Python依赖
├── start.bat           # Windows启动脚本
├── .gitignore          # Git忽略文件
└── README.md           # 项目说明
```

## 开发说明

### 添加新接口

1. 在 `simple_server.py` 中定义Pydantic模型
2. 添加FastAPI路由函数
3. 在 `database.py` 中实现数据库操作
4. 更新API文档

### 数据库连接

使用SQLAlchemy连接PostgreSQL，支持连接池和事务管理。

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！