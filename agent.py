"""
简单的LangGraph Agent
使用千问3max模型和Supabase数据库工具
"""
import os
from dotenv import load_dotenv
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, END
from supabase_tools import DATABASE_TOOLS

# 加载环境变量
load_dotenv()


from langgraph.graph.message import add_messages

# 定义Agent状态
class AgentState(TypedDict):
    """Agent的状态定义"""
    messages: Annotated[Sequence[BaseMessage], add_messages]


# 初始化千问模型
def create_model():
    """
    创建千问3max模型实例
    使用OpenAI兼容接口
    
    Returns:
        配置好的ChatOpenAI实例
    """
    return ChatOpenAI(
        model="qwen-max",  # 千问3max模型
        openai_api_key=os.getenv("QIANWEN_API_KEY"),
        openai_api_base=os.getenv("QIANWEN_BASE_URL"),
        temperature=0.7,  # 控制输出的随机性
        streaming=False
    )


# 创建带工具的模型
model = create_model()
model_with_tools = model.bind_tools(DATABASE_TOOLS)


# 定义系统提示词
# 定义系统提示词
SYSTEM_PROMPT = """你是一个智能助手，可以帮助用户查询和管理Supabase数据库。

你拥有以下能力:
1. 列出数据库中的表 (list_tables)
2. 执行 SQL 语句 (execute_sql) - 可以进行查询、建表、插入等操作。
3. 查看表的结构 (describe_table) - 需要提供表名。

工作流程:
- 理解用户需求
- 如果需要查询或操作数据库，优先使用 SQL 语句
- 给出清晰的回答

注意事项:
- 执行操作前，先通过 list_tables 确认表名
- 结果要格式化，便于用户阅读
"""


def should_continue(state: AgentState) -> str:
    """
    判断是否继续执行工具调用
    
    Args:
        state: 当前Agent状态
        
    Returns:
        "continue" 继续执行工具, "end" 结束对话
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    # 如果最后一条消息有工具调用，继续执行工具
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "continue"
    # 否则结束
    return "end"


def call_model(state: AgentState) -> dict:
    """
    调用模型生成响应
    
    Args:
        state: 当前Agent状态
        
    Returns:
        包含新消息的状态更新
    """
    messages = state["messages"]
    
    # 构建完整的消息列表（包含系统提示）
    full_messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ] + messages
    
    # 调用模型
    response = model_with_tools.invoke(full_messages)
    
    # 返回状态更新
    return {"messages": [response]}


def execute_tools(state: AgentState) -> dict:
    """
    执行工具调用节点
    
    Args:
        state: 当前Agent状态
        
    Returns:
        包含工具执行结果的状态更新
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    # 获取工具调用信息
    tool_calls = last_message.tool_calls
    
    # 创建工具映射
    tools_map = {tool.name: tool for tool in DATABASE_TOOLS}
    
    # 执行每个工具调用
    tool_messages = []
    for tool_call in tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call.get("args", {})
        
        # 调用工具
        if tool_name in tools_map:
            tool = tools_map[tool_name]
            try:
                result = tool.invoke(tool_args)
                tool_messages.append(
                    ToolMessage(
                        content=str(result),
                        tool_call_id=tool_call["id"]
                    )
                )
            except Exception as e:
                tool_messages.append(
                    ToolMessage(
                        content=f"工具执行错误: {str(e)}",
                        tool_call_id=tool_call["id"]
                    )
                )
        else:
            tool_messages.append(
                ToolMessage(
                    content=f"未找到工具: {tool_name}",
                    tool_call_id=tool_call["id"]
                )
            )
    
    return {"messages": tool_messages}


def create_agent_graph():
    """
    创建Agent的工作流图
    
    使用LangGraph构建ReAct循环:
    1. 用户输入 -> 模型推理
    2. 模型决定是否调用工具
    3. 如果需要，执行工具并返回结果
    4. 模型整合工具结果，生成最终回答
    
    Returns:
        编译好的工作流图
    """
    # 创建状态图
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("agent", call_model)       # Agent推理节点
    workflow.add_node("tools", execute_tools)    # 工具执行节点
    
    # 设置入口点
    workflow.set_entry_point("agent")
    
    # 添加条件边: agent -> tools 或 END
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "continue": "tools",  # 需要调用工具
            "end": END            # 直接结束
        }
    )
    
    # 添加边: tools -> agent (工具执行完返回agent)
    workflow.add_edge("tools", "agent")
    
    # 编译工作流
    return workflow.compile()


def run_agent(user_input: str, verbose: bool = True):
    """
    运行Agent处理用户输入
    
    Args:
        user_input: 用户输入的问题
        verbose: 是否打印详细信息
        
    Returns:
        Agent的最终回答
    """
    # 创建Agent图
    app = create_agent_graph()
    
    # 初始化状态
    initial_state = {
        "messages": [HumanMessage(content=user_input)]
    }
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"用户: {user_input}")
        print(f"{'='*60}\n")
    
    # 执行Agent
    final_state = app.invoke(initial_state)
    
    # 获取最终回答
    final_message = final_state["messages"][-1]
    
    if verbose:
        # 打印执行过程
        print("\n执行过程:")
        print("-" * 60)
        for i, msg in enumerate(final_state["messages"], 1):
            if isinstance(msg, HumanMessage):
                print(f"{i}. [用户] {msg.content}")
            elif isinstance(msg, AIMessage):
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    print(f"{i}. [AI-工具调用] 调用了 {len(msg.tool_calls)} 个工具")
                    for tool_call in msg.tool_calls:
                        print(f"   - {tool_call['name']}({tool_call.get('args', {})})")
                else:
                    print(f"{i}. [AI] {msg.content}")
            elif isinstance(msg, ToolMessage):
                print(f"{i}. [工具结果] {msg.content[:100]}...")
        
        print("\n" + "="*60)
        print(f"最终回答:\n{final_message.content}")
        print("="*60 + "\n")
    
    return final_message.content


def main():
    """主函数 - 交互式对话"""
    print("="*60)
    print("欢迎使用智能数据库助手!")
    print("="*60)
    print("\n功能说明:")
    print("- 我可以帮你查询Supabase数据库")
    print("- 输入 'quit' 或 'exit' 退出程序")
    print("- 输入 'help' 查看使用示例\n")
    
    while True:
        try:
            # 获取用户输入
            user_input = input("你: ").strip()
            
            # 退出命令
            if user_input.lower() in ['quit', 'exit', '退出']:
                print("\n再见!")
                break
            
            # 帮助命令    
            if user_input.lower() == 'help':
                print("\n使用示例:")
                print("- '数据库里有哪些表?'")
                print("- '查看users表的结构'")
                print("- '查询users表中的前5条记录'\n")
                continue
            
            # 空输入
            if not user_input:
                continue
            
            # 运行Agent
            run_agent(user_input, verbose=True)
            
        except KeyboardInterrupt:
            print("\n\n程序已中断，再见!")
            break
        except Exception as e:
            print(f"\n错误: {str(e)}\n")


if __name__ == "__main__":
    main()
