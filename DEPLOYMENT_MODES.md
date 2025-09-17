# NL2SQL Agent 部署模式

本项目支持两种部署模式，您可以根据需要选择使用。

## 🚀 模式一：本地工具模式 (当前使用)

### 特点
- ✅ **单进程部署**：只需启动API服务器
- ✅ **无外部依赖**：不需要MCP服务器
- ✅ **高性能**：直接函数调用，无网络延迟
- ✅ **易调试**：所有代码在同一进程中

### 启动方式
```bash
# 只需要启动一个服务
python -m api.api_server
```

### 架构图
```
用户请求 → API Server → 本地工具 → 数据库
```

## 🌐 模式二：MCP模式 (保留备用)

### 特点
- ✅ **分布式部署**：支持多服务器架构
- ✅ **服务解耦**：工具服务独立部署
- ✅ **可扩展性**：支持多Agent共享工具
- ✅ **标准化**：使用MCP协议标准

### 启动方式
```bash
# 需要启动两个服务
# 1. 启动MCP服务器
python -m mcp_server.start_server

# 2. 启动API服务器
python -m api.api_server
```

### 架构图
```
用户请求 → API Server → MCP Client → MCP Server → 数据库工具 → 数据库
```

## 🔄 模式切换指南

### 从本地模式切换到MCP模式

1. **修改 `sql_graph/text2sql_graph.py`**：
   ```python
   # 取消注释MCP相关导入
   from langchain_mcp_adapters.client import MultiServerMCPClient
   from langchain_mcp_adapters.tools import load_mcp_tools
   
   # 取消注释MCP服务器配置
   mcp_server_config = {
       "url": "http://localhost:8000/sse",
       "transport": "sse"
   }
   
   # 在make_graph函数中：
   # 注释本地工具相关代码
   # 取消注释MCP版本代码
   ```

2. **启动MCP服务器**：
   ```bash
   python -m mcp_server.start_server
   ```

### 从MCP模式切换到本地模式

1. **修改 `sql_graph/text2sql_graph.py`**：
   ```python
   # 注释MCP相关导入
   # from langchain_mcp_adapters.client import MultiServerMCPClient
   # from langchain_mcp_adapters.tools import load_mcp_tools
   
   # 注释MCP服务器配置
   # mcp_server_config = { ... }
   
   # 在make_graph函数中：
   # 取消注释本地工具相关代码
   # 注释MCP版本代码
   ```

2. **停止MCP服务器**（如果正在运行）

## 📁 文件说明

### 本地模式相关文件
- `sql_graph/tools_node.py` - 包含本地工具定义
- `sql_graph/text2sql_graph.py` - 工作流定义（当前使用本地工具）

### MCP模式相关文件  
- `mcp_server/mcp_tools.py` - MCP工具定义
- `mcp_server/start_server.py` - MCP服务器启动脚本
- `sql_graph/text2sql_graph.py` - 工作流定义（包含MCP版本的注释代码）

### 通用文件
- `api/api_server.py` - API服务器（两种模式通用）
- `sql_graph/my_llm.py` - LLM配置
- `sql_graph/my_state.py` - 状态定义

## 🎯 推荐使用场景

### 使用本地模式的场景
- 🏠 **单机部署**：所有组件在同一台服务器上
- 🚀 **快速开发**：需要快速迭代和调试
- 📈 **高性能要求**：对响应时间敏感
- 🔧 **简单维护**：希望减少系统复杂度

### 使用MCP模式的场景
- 🌐 **分布式部署**：多台服务器分别部署不同组件
- 🤝 **多Agent系统**：多个AI Agent需要共享工具
- 🔌 **外部集成**：需要集成多个外部API或服务
- 📊 **企业级部署**：需要服务隔离和独立扩展

## ⚠️ 注意事项

1. **数据库配置**：两种模式使用相同的数据库配置，确保连接信息正确
2. **依赖包**：MCP模式需要额外的MCP相关依赖包
3. **端口占用**：MCP模式需要确保8000端口未被占用
4. **日志文件**：两种模式会生成不同的日志文件，注意区分
