# -*- coding: utf-8 -*-
"""
动态工具选择实现

动态工具选择允许 Agent 根据上下文动态决定使用哪些工具，
而不是每次都绑定所有工具。

学习要点：
1. 根据用户意图选择工具子集
2. 减少 LLM 的决策负担
3. 提高工具调用的准确性
4. 可以根据对话历史动态调整

使用场景：
- 根据对话主题切换工具集
- 根据用户权限限制可用工具
- 根据任务类型选择专业工具
- 根据上下文过滤不相关的工具

架构图：
    context_analyzer → tool_selector → agent → tools
         ↓                  ↓
    分析上下文          选择工具子集
    (意图识别)          (动态绑定)
"""

from typing import Annotated, List, Optional
from typing_extensions import TypedDict

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from app.agent.nodes import get_llm
from app.agent.tools import (
    TOOLS,
    TOOL_CATEGORIES,
    get_tools_by_category,
    get_tools_by_names,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


# ============================================================
# 动态工具状态定义
# ============================================================
class DynamicToolsState(TypedDict):
    """
    动态工具选择状态
    
    包含：
    - messages: 对话消息
    - intent: 识别的用户意图
    - selected_tools: 选中的工具名称列表
    - current_tools: 当前绑定的工具实例
    """
    # 消息列表
    messages: Annotated[List[BaseMessage], add_messages]
    
    # 识别的用户意图
    intent: Optional[str]
    
    # 选中的工具名称列表
    selected_tools: List[str]
    
    # 当前绑定的工具实例（不存储在状态中，运行时动态获取）
    current_tools: Optional[list]


# ============================================================
# 意图分类映射
# ============================================================
INTENT_TOOL_MAP = {
    "weather": ["weather"],           # 天气查询 → 天气工具
    "calculation": ["calculation"],   # 数学计算 → 计算工具
    "search": ["search"],             # 信息搜索 → 搜索工具
    "time": ["time"],                 # 时间查询 → 时间工具
    "general": ["search", "time"],    # 一般问题 → 搜索 + 时间
}


# ============================================================
# 节点1: 意图分析节点
# ============================================================
def intent_analyzer_node(state: DynamicToolsState) -> dict:
    """
    意图分析节点 - 识别用户意图
    
    使用 LLM 分析用户消息，识别意图类别。
    
    Args:
        state: 动态工具状态
    
    Returns:
        dict: 状态更新（包含识别的意图）
    
    学习要点：
    - 意图识别是动态工具选择的第一步
    - 可以使用 LLM 进行智能分类
    - 也可以使用规则匹配（更快但不够灵活）
    """
    logger.info("执行意图分析节点")
    
    messages = state.get("messages", [])
    user_message = messages[-1].content if messages else ""
    
    # 使用 LLM 进行意图分类
    llm = get_llm()
    
    classification_prompt = [
        SystemMessage(content=(
            "你是一个意图分类器。分析用户的问题，判断属于哪个意图类别。\n"
            "可选类别：\n"
            "- weather: 天气查询、气温、湿度等\n"
            "- calculation: 数学计算、公式求解等\n"
            "- search: 信息搜索、知识查询、网络搜索等\n"
            "- time: 时间查询、日期、时钟等\n"
            "- general: 一般问题、闲聊等\n\n"
            "只回复类别名称，不要回复其他内容。"
        )),
        AIMessage(content=user_message),
    ]
    
    response = llm.invoke(classification_prompt)
    intent = response.content.strip().lower()
    
    # 确保意图有效
    if intent not in INTENT_TOOL_MAP:
        intent = "general"
    
    logger.info(f"识别意图: {intent}")
    
    return {
        "intent": intent,
        "messages": [AIMessage(content=f"意图识别: {intent}")],
    }


# ============================================================
# 节点2: 工具选择节点
# ============================================================
def tool_selector_node(state: DynamicToolsState) -> dict:
    """
    工具选择节点 - 根据意图选择工具子集
    
    根据识别的意图，从工具分类映射中获取对应的工具。
    
    Args:
        state: 动态工具状态
    
    Returns:
        dict: 状态更新（包含选中的工具名称）
    
    学习要点：
    - 工具选择可以基于规则（如本示例）
    - 也可以使用 LLM 动态决定
    - 选中的工具会绑定到 LLM
    """
    logger.info("执行工具选择节点")
    
    intent = state.get("intent", "general")
    
    # 根据意图获取工具类别
    tool_categories = INTENT_TOOL_MAP.get(intent, ["general"])
    
    # 获取工具实例
    selected_tools = []
    for category in tool_categories:
        if category in TOOL_CATEGORIES:
            tool_names = [t.name for t in TOOL_CATEGORIES[category]]
            selected_tools.extend(tool_names)
    
    logger.info(f"选择工具: {selected_tools}")
    
    return {
        "selected_tools": selected_tools,
    }


# ============================================================
# 节点3: Agent 推理节点（动态绑定工具）
# ============================================================
def agent_node_with_dynamic_tools(state: DynamicToolsState) -> dict:
    """
    Agent 节点 - 使用动态选择的工具进行推理
    
    与基础 Agent 的区别：
    - 不是绑定所有工具
    - 只绑定根据意图选择的工具子集
    
    Args:
        state: 动态工具状态
    
    Returns:
        dict: 状态更新
    
    学习要点：
    - 动态绑定工具可以减少 LLM 的决策负担
    - 提高工具调用的准确性
    - 避免 LLM 选择不相关的工具
    """
    logger.info("执行 Agent 节点（动态工具）")
    
    messages = state.get("messages", [])
    selected_tool_names = state.get("selected_tools", [])
    
    # 获取选中的工具实例
    current_tools = get_tools_by_names(selected_tool_names)
    
    if not current_tools:
        logger.warning("没有选中工具，使用默认工具")
        current_tools = TOOLS
    
    logger.info(f"绑定工具: {[t.name for t in current_tools]}")
    
    # 获取 LLM 并绑定选中的工具
    llm = get_llm()
    llm_with_tools = llm.bind_tools(current_tools)
    
    # 调用 LLM
    response = llm_with_tools.invoke(messages)
    
    # 记录工具调用
    tool_calls = []
    if hasattr(response, "tool_calls") and response.tool_calls:
        tool_calls = [
            {"name": tc["name"], "args": tc["args"]}
            for tc in response.tool_calls
        ]
        logger.info(f"LLM 请求调用工具: {tool_calls}")
    
    return {
        "messages": [response],
        "current_tools": current_tools,
    }


# ============================================================
# 节点4: 工具执行节点
# ============================================================
def tool_node_dynamic(state: DynamicToolsState) -> dict:
    """
    工具执行节点 - 执行动态选择的工具
    
    与基础 tool_node 类似，但使用动态选择的工具。
    
    Args:
        state: 动态工具状态
    
    Returns:
        dict: 状态更新
    """
    logger.info("执行工具节点（动态工具）")
    
    messages = state.get("messages", [])
    last_message = messages[-1] if messages else None
    
    if not last_message or not hasattr(last_message, "tool_calls"):
        return {}
    
    # 获取当前可用的工具
    current_tools = state.get("current_tools", TOOLS)
    
    # 执行工具调用
    from langchain_core.messages import ToolMessage
    
    tool_results = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        
        # 查找工具
        tool = next((t for t in current_tools if t.name == tool_name), None)
        if not tool:
            tool_results.append({
                "tool_call_id": tool_call["id"],
                "name": tool_name,
                "content": f"错误: 工具 '{tool_name}' 不在当前可用工具列表中",
            })
            continue
        
        # 执行工具
        try:
            result = tool.invoke(tool_args)
            tool_results.append({
                "tool_call_id": tool_call["id"],
                "name": tool_name,
                "content": str(result),
            })
        except Exception as e:
            tool_results.append({
                "tool_call_id": tool_call["id"],
                "name": tool_name,
                "content": f"工具执行失败: {e}",
            })
    
    # 构造 ToolMessage 列表
    tool_messages = [
        ToolMessage(
            content=tr["content"],
            tool_call_id=tr["tool_call_id"],
            name=tr["name"],
        )
        for tr in tool_results
    ]
    
    return {
        "messages": tool_messages,
    }


# ============================================================
# 路由函数
# ============================================================
def should_use_tools(state: DynamicToolsState) -> str:
    """
    判断是否需要执行工具
    
    Args:
        state: 动态工具状态
    
    Returns:
        str: 下一个节点名称
    """
    messages = state.get("messages", [])
    last_message = messages[-1] if messages else None
    
    if last_message and hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    
    return "end"


# ============================================================
# 构建动态工具图
# ============================================================
def build_dynamic_tools_graph():
    """
    构建动态工具选择图
    
    流程：
        START → intent_analyzer → tool_selector → agent → should_use_tools
                                                              │
                                                              ├─ 有工具调用 → tools → agent
                                                              └─ 无工具调用 → END
    
    学习要点：
    - 意图分析和工具选择是额外的预处理步骤
    - Agent 只绑定选中的工具子集
    - 这种模式可以提高工具调用的准确性
    
    Returns:
        CompiledGraph: 编译后的动态工具图
    """
    logger.info("构建动态工具选择图")
    
    # 创建状态图
    workflow = StateGraph(DynamicToolsState)
    
    # 添加节点
    workflow.add_node("intent_analyzer", intent_analyzer_node)
    workflow.add_node("tool_selector", tool_selector_node)
    workflow.add_node("agent", agent_node_with_dynamic_tools)
    workflow.add_node("tools", tool_node_dynamic)
    
    # 设置入口点
    workflow.set_entry_point("intent_analyzer")
    
    # 添加边
    workflow.add_edge("intent_analyzer", "tool_selector")
    workflow.add_edge("tool_selector", "agent")
    
    # agent → should_use_tools（条件路由）
    workflow.add_conditional_edges(
        "agent",
        should_use_tools,
        {
            "tools": "tools",
            "end": END,
        }
    )
    
    # tools → agent（循环）
    workflow.add_edge("tools", "agent")
    
    # 编译图
    graph = workflow.compile()
    
    logger.info("动态工具选择图构建完成")
    return graph


# 全局图实例
dynamic_tools_graph = build_dynamic_tools_graph()


# ============================================================
# 使用示例
# ============================================================
"""
使用示例：

# 1. 准备初始状态
initial_state = {
    "messages": [HumanMessage(content="北京今天天气怎么样？")],
    "intent": None,
    "selected_tools": [],
    "current_tools": None,
}

# 2. 执行动态工具图
result = dynamic_tools_graph.invoke(initial_state)

# 3. 流程：
# - intent_analyzer: 识别意图为 "weather"
# - tool_selector: 选择天气工具
# - agent: 只绑定天气工具，调用 get_weather
# - tools: 执行天气查询
# - agent: 根据结果生成回答
"""
