# LangChain Agent with Tongyi Qianwen (通义千问)

一个功能完整的 LangChain Agent 实现，展示了 LangChain 的核心功能和常见的 Agent 能力。

A comprehensive LangChain Agent implementation demonstrating core LangChain features and common agent capabilities.

## ✨ 特性 (Features)

### 🤖 核心功能
- **LLM 集成**: 阿里云通义千问 (Tongyi Qianwen)
- **Agent 模式**: ReAct (Reasoning + Acting) 模式
- **对话记忆**: 自动维护对话上下文
- **错误处理**: 完善的错误处理和重试机制
- **中英文双语**: 支持中英文提示词和对话

### 🛠️ 内置工具 (Built-in Tools)

1. **计算器 (Calculator)** - 安全的数学表达式计算
2. **时间工具 (DateTime)** - 获取当前日期和时间
3. **文件读取 (Read File)** - 读取文件内容
4. **文件写入 (Write File)** - 写入内容到文件
5. **目录列表 (List Directory)** - 列出目录内容
6. **天气查询 (Weather)** - 获取天气信息（演示版）
7. **维基百科搜索 (Wikipedia)** - 搜索维基百科

### ⛓️ Chain 示例 (Chain Examples)

- **LLMChain**: 基础链式调用
- **SequentialChain**: 多步骤顺序执行
- **翻译链 (Translation)**: 文本翻译
- **摘要链 (Summarization)**: 文本摘要

## 📋 前置要求 (Prerequisites)

- Python 3.8+
- 阿里云 DashScope API Key

## 🚀 快速开始 (Quick Start)

### 1. 安装依赖 (Install Dependencies)

\`\`\`bash
pip install -r requirements.txt
\`\`\`

### 2. 配置 API Key

复制环境变量模板：
\`\`\`bash
cp .env.example .env
\`\`\`

编辑 `.env` 文件，填入你的 DashScope API Key：
\`\`\`
DASHSCOPE_API_KEY=your_api_key_here
\`\`\`

**获取 API Key**: 访问 [阿里云 DashScope 控制台](https://dashscope.console.aliyun.com/)

### 3. 运行演示 (Run Demo)

\`\`\`bash
# 交互式模式
python main.py

# 或者选择特定演示
python main.py basic      # 基础查询演示
python main.py workflow   # 复杂工作流演示
python main.py memory     # 记忆功能演示
python main.py file       # 文件操作演示
python main.py wiki       # 维基百科搜索
python main.py all        # 运行所有演示
\`\`\`

### 4. 运行 Chain 示例

\`\`\`bash
python chains_example.py
\`\`\`

## 📁 项目结构 (Project Structure)

\`\`\`
project-Life/
├── langchain_agent.py      # 主 Agent 实现
├── custom_tools.py         # 自定义工具库
├── chains_example.py       # Chain 示例集合
├── main.py                 # 演示和交互程序
├── requirements.txt        # 项目依赖
├── .env.example           # 环境变量模板
└── README.md              # 本文件
\`\`\`

## 💡 使用示例 (Usage Examples)

### 基础使用

\`\`\`python
from langchain_agent import create_agent

# 创建 agent
agent = create_agent(verbose=True)

# 简单对话
response = agent.chat("现在几点了？")
print(response)

# 计算
response = agent.chat("帮我计算 123 * 456")
print(response)
\`\`\`

### 使用自定义工具

\`\`\`python
from langchain_agent import TongyiAgent

# 创建带自定义配置的 agent
agent = TongyiAgent(
    model_name="qwen-plus",  # 使用 qwen-plus 模型
    temperature=0.7,
    verbose=True
)

# 文件操作
response = agent.chat("列出当前目录的文件")
print(response)

# 维基百科搜索
response = agent.chat("搜索维基百科：人工智能")
print(response)
\`\`\`

### Chain 示例

\`\`\`python
from langchain_community.llms import Tongyi
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
import os

llm = Tongyi(dashscope_api_key=os.getenv("DASHSCOPE_API_KEY"))

template = "请用一句话解释：{concept}"
prompt = PromptTemplate(input_variables=["concept"], template=template)

chain = LLMChain(llm=llm, prompt=prompt)
result = chain.run(concept="LangChain")
print(result)
\`\`\`

## 🔧 配置选项 (Configuration)

### 模型选择

在 `.env` 中设置：
\`\`\`
QWEN_MODEL=qwen-turbo    # 标准版（推荐）
# QWEN_MODEL=qwen-plus   # 增强版
# QWEN_MODEL=qwen-max    # 旗舰版
\`\`\`

### Agent 参数

\`\`\`python
agent = TongyiAgent(
    model_name="qwen-turbo",   # 模型名称
    temperature=0.7,           # 温度 (0-1)
    max_iterations=10,         # 最大迭代次数
    verbose=True               # 显示详细日志
)
\`\`\`

## 📚 主要概念 (Key Concepts)

### 1. Agent (代理)
Agent 是能够使用工具并进行推理的 LLM。本项目使用 ReAct 模式，让 Agent 能够：
- **推理 (Reasoning)**: 思考需要做什么
- **行动 (Acting)**: 调用工具执行任务
- **观察 (Observing)**: 查看工具返回结果
- **迭代**: 重复上述过程直到完成任务

### 2. Tools (工具)
工具是 Agent 可以调用的函数。每个工具都有：
- 名称 (Name)
- 描述 (Description) - Agent 用来决定何时使用该工具
- 输入参数 (Input)
- 返回值 (Output)

### 3. Memory (记忆)
记忆允许 Agent 记住之前的对话内容，实现上下文感知的对话。

### 4. Chains (链)
Chain 是将多个步骤连接起来的方式，可以实现复杂的工作流。

## 🛠️ 自定义工具 (Custom Tools)

创建自定义工具很简单：

\`\`\`python
from langchain.tools import tool

@tool
def my_custom_tool(input_text: str) -> str:
    """
    工具描述 - Agent 会根据这个描述决定何时使用此工具
    """
    # 你的逻辑
    result = f"处理结果: {input_text}"
    return result
\`\`\`

然后添加到 Agent：

\`\`\`python
from custom_tools import ALL_TOOLS

# 添加你的工具
ALL_TOOLS.append(my_custom_tool)

# 创建 agent
agent = create_agent()
\`\`\`

## 🐛 故障排除 (Troubleshooting)

### 问题：ImportError: No module named 'dashscope'

**解决方案**: 
\`\`\`bash
pip install dashscope
\`\`\`

### 问题：API Key 错误

**解决方案**: 
1. 确保 `.env` 文件存在且包含正确的 API key
2. 检查 API key 是否有效
3. 确认已在阿里云开通 DashScope 服务

### 问题：Wikipedia 搜索失败

**解决方案**: 
\`\`\`bash
pip install wikipedia
\`\`\`

## 📖 更多资源 (Resources)

- [LangChain 官方文档](https://python.langchain.com/)
- [阿里云 DashScope 文档](https://help.aliyun.com/zh/dashscope/)
- [通义千问模型介绍](https://tongyi.aliyun.com/)

## 📝 许可证 (License)

MIT License

## 🤝 贡献 (Contributing)

欢迎提交 Issue 和 Pull Request！

---

**享受使用 LangChain 和通义千问构建智能应用！** 🎉
