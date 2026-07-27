# -*- coding: utf-8 -*-
"""
人机协作（Interrupt）实现

人机协作是 LangGraph 的核心高级特性之一。
它允许 Agent 在执行过程中暂停，等待人工确认后再继续。

学习要点：
1. 使用 interrupt() 函数暂停执行
2. 使用 Command(resume=...) 恢复执行
3. 状态会被持久化，即使进程重启也能恢复
4. 适用于敏感操作、审批流程、人工审核等场景

使用场景：
- 敏感操作前需要人工确认（如删除数据、发送邮件）
- 需要人工提供额外信息
- 审批流程（如请假、报销）
- 人工审核 AI 生成的内容

架构图：
    agent → should_review → [interrupt] → human_review → tools → agent
                              ↓
                         暂停等待人工输入
                              ↓
                         Command(resume="approve") 恢复执行
"""

from typing import Annotated, List, Optional
from typing_extensions import TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.types import interrupt, Command

from app.agent.nodes import get_llm
from app.agent.tools import TOOLS
from app.core.logging import get_logger

logger = get_logger(__name__)


# ============================================================
# 人机协作状态定义
# ============================================================
class InterruptState(TypedDict):
    """
    人机协作状态
    
    包含：
    - messages: 对话消息
    - pending_action: 待确认的操作
    - human_feedback: 人工反馈
    - approved: 是否已批准
    """
    # 消息列表
    messages: Annotated[List[BaseMessage], add_messages]
    
    # 待确认的操作（工具调用信息）
    pending_action: Optional[dict]
    
    # 人工反馈
    human_feedback: Optional[str]
    
    # 是否已批准
    approved: bool


# ============================================================
# 节点1: Agent 推理节点
# ============================================================
def agent_node_with_interrupt(state: InterruptState) -> dict:
    """
    Agent 节点 - 调用 LLM 进行推理
    
    与基础 Agent 类似，但会在有工具调用时触发 interrupt。
    
    Args:
        state: 人机协作状态
    
    Returns:
        dict: 状态更新
    """
    logger.info("执行 Agent 节点（人机协作模式）")
    
    messages = state.get("messages", [])
    
    # 获取 LLM 并绑定工具
    llm = get_llm()
    llm_with_tools = llm.bind_tools(TOOLS)
    
    # 调用 LLM
    response = llm_with_tools.invoke(messages)
    
    # 检查是否有工具调用
    tool_calls = []
    if hasattr(response, "tool_calls") and response.tool_calls:
        tool_calls = [
            {"name": tc["name"], "args": tc["args"]}
            for tc in response.tool_calls
        ]
        logger.info(f"LLM 请求调用工具: {tool_calls}")
    
    return {
        "messages": [response],
        "pending_action": tool_calls[0] if tool_calls else None,
        "approved": False,
    }


# ============================================================
# 节点2: 人机审核节点（使用 interrupt）
# ============================================================
def human_review_node(state: InterruptState) -> dict:
    """
    人机审核节点 - 暂停等待人工确认
    
    这是人机协作的核心节点。
    使用 interrupt() 暂停执行，等待人工输入。
    
    流程：
    1. 调用 interrupt() 暂停执行
    2. 系统保存当前状态
    3. 等待外部调用 Command(resume=...) 恢复
    4. 恢复后继续执行
    
    Args:
        state: 人机协作状态
    
    Returns:
        dict: 状态更新
    
    学习要点：
    - interrupt() 会暂停图的执行
    - interrupt() 的参数会返回给调用方
    - 恢复时通过 Command(resume=...) 传入人工反馈
    - 状态会被持久化，可以跨进程恢复
    """
    logger.info("执行人机审核节点 - 暂停等待人工确认")
    
    pending_action = state.get("pending_action")
    
    if not pending_action:
        logger.info("没有待确认的操作，跳过审核")
        return {"approved": True}
    
    # 构造审核信息
    review_info = {
        "question": "Agent 请求执行以下操作，是否允许？",
        "tool_name": pending_action.get("name", "unknown"),
        "tool_args": pending_action.get("args", {}),
        "instructions": "请回复 'approve' 批准，或 'reject' 拒绝，或提供修改建议",
    }
    
    # 暂停执行，等待人工输入
    # interrupt() 会：
    # 1. 保存当前状态
    # 2. 返回 review_info 给调用方
    # 3. 等待 Command(resume=...) 恢复
    human_feedback = interrupt(review_info)
    
    logger.info(f"收到人工反馈: {human_feedback}")
    
    # 处理人工反馈
    if human_feedback == "approve":
        return {
            "approved": True,
            "human_feedback": "已批准",
            "messages": [AIMessage(content="✅ 人工已批准执行该操作")],
        }
    elif human_feedback == "reject":
        return {
            "approved": False,
            "human_feedback": "已拒绝",
            "messages": [AIMessage(content="❌ 人工已拒绝执行该操作")],
        }
    else:
        # 人工提供了修改建议
        return {
            "approved": False,
            "human_feedback": human_feedback,
            "messages": [AIMessage(content=f"💬 人工反馈: {human_feedback}")],
        }


# ============================================================
# 节点3: 工具执行节点
# ============================================================
def tool_node_with_interrupt(state: InterruptState) -> dict:
    """
    工具执行节点 - 只有在批准后才执行工具
    
    这个节点会检查 approved 状态：
    - 如果 approved=True，执行工具
    - 如果 approved=False，跳过执行
    
    Args:
        state: 人机协作状态
    
    Returns:
        dict: 状态更新
    """
    logger.info("执行工具节点（人机协作模式）")
    
    approved = state.get("approved", False)
    
    if not approved:
        logger.info("操作未获批准，跳过工具执行")
        return {
            "messages": [AIMessage(content="操作已取消")],
            "pending_action": None,
        }
    
    # 执行工具（与基础 tool_node 类似）
    messages = state.get("messages", [])
    last_message = messages[-1] if messages else None
    
    if not last_message or not hasattr(last_message, "tool_calls"):
        return {"pending_action": None}
    
    tool_results = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        
        # 查找工具
        tool = next((t for t in TOOLS if t.name == tool_name), None)
        if not tool:
            tool_results.append(f"错误: 未找到工具 '{tool_name}'")
            continue
        
        # 执行工具
        try:
            result = tool.invoke(tool_args)
            tool_results.append(str(result))
        except Exception as e:
            tool_results.append(f"工具执行失败: {e}")
    
    return {
        "messages": [AIMessage(content="\n".join(tool_results))],
        "pending_action": None,
    }


# ============================================================
# 路由函数
# ============================================================
def should_review(state: InterruptState) -> str:
    """
    判断是否需要人工审核
    
    路由规则：
    - 有 pending_action → 需要审核 → human_review
    - 无 pending_action → 直接结束 → end
    
    Args:
        state: 人机协作状态
    
    Returns:
        str: 下一个节点名称
    """
    pending_action = state.get("pending_action")
    
    if pending_action:
        logger.info("有待确认的操作，路由到人工审核")
        return "human_review"
    
    logger.info("没有待确认的操作，直接结束")
    return "end"


def after_review_route(state: InterruptState) -> str:
    """
    人工审核后路由
    
    路由规则：
    - approved=True → 执行工具 → tools
    - approved=False → 结束 → end
    
    Args:
        state: 人机协作状态
    
    Returns:
        str: 下一个节点名称
    """
    approved = state.get("approved", False)
    
    if approved:
        logger.info("操作已批准，路由到工具执行")
        return "tools"
    
    logger.info("操作未批准，结束执行")
    return "end"


# ============================================================
# 构建人机协作图
# ============================================================
def build_interrupt_graph():
    """
    构建人机协作图
    
    流程：
        START → agent → should_review → human_review → after_review
                    │                                        │
                    └─ 无工具调用 → END                      ├─ 批准 → tools → END
                                                             └─ 拒绝 → END
    
    学习要点：
    - interrupt() 在 human_review 节点中暂停执行
    - 状态会被持久化到 checkpointer
    - 外部通过 Command(resume=...) 恢复执行
    - 可以跨进程、跨重启恢复
    
    Returns:
        CompiledGraph: 编译后的人机协作图
    """
    logger.info("构建人机协作图")
    
    # 创建状态图
    workflow = StateGraph(InterruptState)
    
    # 添加节点
    workflow.add_node("agent", agent_node_with_interrupt)
    workflow.add_node("human_review", human_review_node)
    workflow.add_node("tools", tool_node_with_interrupt)
    
    # 设置入口点
    workflow.set_entry_point("agent")
    
    # agent → should_review（判断是否需要人工审核）
    workflow.add_conditional_edges(
        "agent",
        should_review,
        {
            "human_review": "human_review",
            "end": END,
        }
    )
    
    # human_review → after_review（根据审核结果路由）
    workflow.add_conditional_edges(
        "human_review",
        after_review_route,
        {
            "tools": "tools",
            "end": END,
        }
    )
    
    # tools → END
    workflow.add_edge("tools", END)
    
    # 编译图（必须使用 checkpointer，因为 interrupt 需要持久化状态）
    from app.memory import memory_manager
    
    graph = workflow.compile(
        checkpointer=memory_manager.checkpointer
    )
    
    logger.info("人机协作图构建完成")
    return graph


# 全局图实例
interrupt_graph = build_interrupt_graph()


# ============================================================
# 使用示例
# ============================================================
"""
使用示例：

# 1. 启动对话
config = {"configurable": {"thread_id": "conv-123"}}
initial_state = {
    "messages": [HumanMessage(content="查询北京天气")],
    "pending_action": None,
    "human_feedback": None,
    "approved": False,
}

# 2. 执行到 interrupt 暂停
result = interrupt_graph.invoke(initial_state, config)
# 此时图会暂停在 human_review 节点
# 返回 interrupt 信息

# 3. 人工审核并恢复执行
# 方式A：批准
interrupt_graph.invoke(Command(resume="approve"), config)

# 方式B：拒绝
interrupt_graph.invoke(Command(resume="reject"), config)

# 方式C：提供修改建议
interrupt_graph.invoke(Command(resume="请使用摄氏度"), config)
"""
