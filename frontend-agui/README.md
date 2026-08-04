# AG-UI 前端项目

基于 AG-UI 协议的前端应用，通过 LangGraph Advanced 调用 MCP 和 A2A 服务。

## 📋 项目概述

这是一个完整的前端实现，展示了如何通过 AG-UI 协议与后端智能体进行交互。项目采用 Vue 3 + Vite 构建，实现了：

- **AG-UI 协议客户端**：支持所有 AG-UI 事件类型
- **实时流式对话**：通过 SSE 接收后端事件流
- **工具调用可视化**：展示 MCP 和 A2A 工具调用过程
- **状态管理**：轻量级状态管理器
- **调试面板**：实时显示事件日志和 Agent 状态

## 🏗️ 项目结构

```
frontend-agui/
├── index.html              # 入口 HTML
├── package.json            # 项目配置
├── vite.config.js          # Vite 配置
├── .env                    # 环境变量
├── .gitignore             # Git 忽略文件
├── README.md              # 项目文档
│
└── src/
    ├── main.js            # 应用入口
    ├── App.vue            # 根组件
    │
    ├── core/              # 核心模块
    │   ├── agui-client.js      # AG-UI 客户端
    │   ├── state-manager.js    # 状态管理器
    │   └── event-handler.js    # 事件处理器
    │
    ├── services/          # 服务层
    │   └── chat-service.js     # 聊天服务
    │
    ├── components/        # UI 组件
    │   ├── ChatWindow.vue      # 聊天窗口
    │   ├── MessageList.vue     # 消息列表
    │   ├── MessageInput.vue    # 消息输入
    │   ├── ToolCallCard.vue    # 工具调用卡片
    │   ├── AgentStatus.vue     # Agent 状态
    │   └── EventLog.vue        # 事件日志
    │
    └── styles/            # 样式文件
        └── main.css            # 全局样式
```

## 🚀 快速开始

### 1. 安装依赖

```bash
cd frontend-agui
npm install
```

### 2. 配置环境变量

编辑 `.env` 文件，配置后端 API 地址：

```env
# 后端 API 地址
VITE_API_BASE_URL=http://localhost:8000

# 调试模式
VITE_DEBUG=true
```

### 3. 启动后端服务

确保以下服务已启动：

```bash
# 启动 LangGraph Advanced (端口 8000)
cd langgraph_advanced
python main.py

# 启动 MCP Server (端口 8001)
cd mcp_server
python main.py

# 启动 A2A Server (端口 8002)
cd a2a_server
python main.py
```

### 4. 启动前端开发服务器

```bash
npm run dev
```

访问 http://localhost:5173 即可使用。

## 📖 功能说明

### 1. AG-UI 协议支持

支持以下 AG-UI 事件类型：

- `RunStarted` / `RunFinished`：运行开始/结束
- `TextMessageStart` / `TextMessageContent` / `TextMessageEnd`：文本消息流
- `ToolCallStart` / `ToolCallArgs` / `ToolCallEnd`：工具调用流
- `StateDelta`：状态更新
- `StepStarted` / `StepFinished`：步骤开始/结束

### 2. 三种运行模式

- **单 Agent 模式**：使用基础 Agent 处理请求
- **多 Agent 模式**：使用多 Agent 协作系统
- **Master Graph 模式**：使用统一大图，集成所有高级功能

### 3. 工具调用可视化

当 Agent 调用 MCP 或 A2A 工具时，界面会实时显示：

- 工具名称和参数
- 执行状态（运行中/已完成/失败）
- 执行结果

### 4. 调试面板

右侧调试面板显示：

- **Agent 状态**：当前执行步骤、运行状态、进度
- **事件日志**：所有 AG-UI 事件的实时日志

## 🔧 开发指南

### 修改后端 API 地址

编辑 `.env` 文件：

```env
VITE_API_BASE_URL=http://your-backend-url:port
```

### 添加新的组件

在 `src/components/` 目录下创建新的 Vue 组件文件。

### 自定义样式

编辑 `src/styles/main.css` 或在各组件的 `<style>` 标签中定义样式。

## 📝 注意事项

1. **后端服务必须先启动**：前端依赖 LangGraph Advanced、MCP Server 和 A2A Server
2. **端口配置**：确保后端服务使用正确的端口（8000、8001、8002）
3. **CORS 配置**：后端已配置允许前端跨域访问
4. **环境变量**：生产环境需要修改 `.env` 中的 API 地址

## 🐛 故障排查

### 前端无法连接后端

1. 检查后端服务是否启动
2. 检查 `.env` 中的 `VITE_API_BASE_URL` 是否正确
3. 检查浏览器控制台是否有 CORS 错误
4. 检查后端日志是否有错误信息

### 工具调用不显示

1. 检查后端是否正确返回 AG-UI 事件
2. 检查浏览器控制台是否有 JavaScript 错误
3. 检查事件日志面板是否有相关事件

### 页面样式异常

1. 清除浏览器缓存
2. 检查 CSS 文件是否正确加载
3. 检查浏览器开发者工具的控制台错误

## 📚 技术栈

- **Vue 3**：前端框架
- **Vite**：构建工具
- **AG-UI 协议**：智能体通信协议
- **SSE**：服务器推送事件
- **CSS3**：样式和动画

## 📄 许可证

MIT License
