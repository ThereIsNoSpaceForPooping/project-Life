# -*- coding: utf-8 -*-
"""
时间旅行（Time Travel）实现

时间旅行是 LangGraph 的强大调试和回溯功能。
它允许查看历史状态、回退到某个时间点、从历史状态重新执行。

学习要点：
1. get_state_history() - 获取所有历史状态
2. get_state() - 获取当前状态
3. update_state() - 修改某个历史状态
4. 从历史状态重新执行
5. 需要 checkpointer 支持（状态必须持久化）

使用场景：
- 调试：查看 Agent 执行的每一步
- 回溯：回退到某个历史状态重新执行
- 分支：从历史状态创建新的执行分支
- 审计：记录完整的执行历史

架构图：
    执行流程: START → node1 → node2 → node3 → END
                  ↓        ↓        ↓        ↓
              checkpoint checkpoint checkpoint checkpoint
                  ↓        ↓        ↓        ↓
              state_1  state_2  state_3  state_4
    
    时间旅行:
    - get_state_history() → [state_1, state_2, state_3, state_4]
    - update_state(config, new_values, as_node="node2") → 修改 state_2
    - invoke(None, config) → 从修改后的 state_2 重新执行
"""

from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from app.agent.nodes import get_llm
from app.memory import memory_manager
from app.core.logging import get_logger

logger = get_logger(__name__)


# ============================================================
# 时间旅行状态定义
# ============================================================
class TimeTravelState(TypedDict):
    """
    时间旅行状态
    
    包含：
    - messages: 对话消息
    - step: 当前步骤编号
    - data: 中间数据（用于演示状态修改）
    """
    # 消息列表
    messages: Annotated[List[BaseMessage], add_messages]
    
    # 当前步骤编号
    step: int
    
    # 中间数据
    data: Optional[str]


# ============================================================
# 节点定义（用于演示时间旅行）
# ============================================================
def step1_node(state: TimeTravelState) -> dict:
    """
    步骤1节点 - 数据收集
    
    这是执行流程的第一步，负责收集初始数据。
    """
    logger.info("执行步骤1: 数据收集")
    
    messages = state.get("messages", [])
    query = messages[-1].content if messages else ""
    
    # 模拟数据收集
    collected_data = f"收集到关于 '{query}' 的初始数据"
    
    return {
        "step": 1,
        "data": collected_data,
        "messages": [AIMessage(content=f"步骤1完成: {collected_data}")],
    }


def step2_node(state: TimeTravelState) -> dict:
    """
    步骤2节点 - 数据分析
    
    这是执行流程的第二步，负责分析收集到的数据。
    """
    logger.info("执行步骤2: 数据分析")
    
    data = state.get("data", "")
    
    # 模拟数据分析
    analyzed_data = f"{data} → 分析完成"
    
    return {
        "step": 2,
        "data": analyzed_data,
        "messages": [AIMessage(content=f"步骤2完成: {analyzed_data}")],
    }


def step3_node(state: TimeTravelState) -> dict:
    """
    步骤3节点 - 结果生成
    
    这是执行流程的第三步，负责生成最终结果。
    """
    logger.info("执行步骤3: 结果生成")
    
    data = state.get("data", "")
    
    # 模拟结果生成
    final_result = f"{data} → 生成最终报告"
    
    return {
        "step": 3,
        "data": final_result,
        "messages": [AIMessage(content=f"步骤3完成: {final_result}")],
    }


# ============================================================
# 构建时间旅行演示图
# ============================================================
def build_time_travel_graph():
    """
    构建时间旅行演示图
    
    流程：
        START → step1 → step2 → step3 → END
    
    每个节点执行后都会创建 checkpoint，
    允许后续进行时间旅行操作。
    
    Returns:
        CompiledGraph: 编译后的时间旅行图
    """
    logger.info("构建时间旅行演示图")
    
    # 创建状态图
    workflow = StateGraph(TimeTravelState)
    
    # 添加节点
    workflow.add_node("step1", step1_node)
    workflow.add_node("step2", step2_node)
    workflow.add_node("step3", step3_node)
    
    # 设置入口点
    workflow.set_entry_point("step1")
    
    # 添加边（线性流程）
    workflow.add_edge("step1", "step2")
    workflow.add_edge("step2", "step3")
    workflow.add_edge("step3", END)
    
    # 编译图（必须使用 checkpointer）
    graph = workflow.compile(
        checkpointer=memory_manager.checkpointer
    )
    
    logger.info("时间旅行演示图构建完成")
    return graph


# 全局图实例
time_travel_graph = build_time_travel_graph()


# ============================================================
# 时间旅行工具函数
# ============================================================
def get_execution_history(config: dict) -> List[Dict[str, Any]]:
    """
    获取执行历史
    
    返回所有历史状态，按时间顺序排列。
    
    Args:
        config: 配置（包含 thread_id）
    
    Returns:
        List[Dict]: 历史状态列表
    
    学习要点：
    - get_state_history() 返回所有 checkpoint
    - 每个 checkpoint 包含：
      - values: 状态值
      - next: 下一个要执行的节点
      - config: checkpoint 配置
      - metadata: 元数据（时间戳等）
    """
    logger.info(f"获取执行历史: {config}")
    
    history = []
    
    # 遍历所有历史状态
    for state_snapshot in time_travel_graph.get_state_history(config):
        history.append({
            "values": state_snapshot.values,
            "next": state_snapshot.next,
            "config": state_snapshot.config,
            "metadata": state_snapshot.metadata,
            "created_at": state_snapshot.created_at,
            "parent_config": state_snapshot.parent_config,
        })
    
    logger.info(f"获取到 {len(history)} 个历史状态")
    return history


def get_current_state(config: dict) -> Dict[str, Any]:
    """
    获取当前状态
    
    Args:
        config: 配置（包含 thread_id）
    
    Returns:
        Dict: 当前状态
    """
    logger.info(f"获取当前状态: {config}")
    
    state_snapshot = time_travel_graph.get_state(config)
    
    return {
        "values": state_snapshot.values,
        "next": state_snapshot.next,
        "config": state_snapshot.config,
        "metadata": state_snapshot.metadata,
    }


def update_state_at_step(
    config: dict,
    new_values: Dict[str, Any],
    as_node: str
) -> Dict[str, Any]:
    """
    修改历史状态
    
    在指定的节点处修改状态，然后可以从修改后的状态重新执行。
    
    Args:
        config: 配置（包含 thread_id）
        new_values: 新的状态值
        as_node: 在哪个节点处修改
    
    Returns:
        Dict: 更新后的状态
    
    学习要点：
    - update_state() 创建一个新的 checkpoint
    - 这个 checkpoint 会覆盖指定的历史状态
    - 后续调用 invoke() 会从修改后的状态继续执行
    - 这实现了"分支"功能
    """
    logger.info(f"修改历史状态: node={as_node}, values={new_values}")
    
    # 更新状态
    time_travel_graph.update_state(
        config,
        new_values,
        as_node=as_node
    )
    
    # 返回更新后的状态
    return get_current_state(config)


def replay_from_step(config: dict) -> Dict[str, Any]:
    """
    从当前状态重新执行
    
    从当前状态（可能是修改后的）继续执行到结束。
    
    Args:
        config: 配置（包含 thread_id）
    
    Returns:
        Dict: 最终状态
    
    学习要点：
    - invoke(None, config) 从当前状态继续执行
    - 如果状态被修改过，会从修改后的状态执行
    - 这实现了"重新执行"功能
    """
    logger.info(f"从当前状态重新执行: {config}")
    
    # 从当前状态继续执行
    result = time_travel_graph.invoke(None, config)
    
    return result


# ============================================================
# 使用示例
# ============================================================
"""
使用示例：

# 1. 初始执行
config = {"configurable": {"thread_id": "conv-123"}}
initial_state = {
    "messages": [HumanMessage(content="分析 Python 教程")],
    "step": 0,
    "data": None,
}

result = time_travel_graph.invoke(initial_state, config)
print("初始执行完成")

# 2. 查看执行历史
history = get_execution_history(config)
for i, state in enumerate(history):
    print(f"状态 {i}: step={state['values'].get('step')}, next={state['next']}")

# 3. 获取当前状态
current = get_current_state(config)
print(f"当前步骤: {current['values'].get('step')}")

# 4. 修改历史状态（回退到 step1 并修改数据）
update_state_at_step(
    config,
    {"data": "修改后的数据", "step": 1},
    as_node="step1"
)

# 5. 从修改后的状态重新执行
result = replay_from_step(config)
print("重新执行完成")

# 6. 查看新的执行历史
new_history = get_execution_history(config)
print(f"新的历史状态数: {len(new_history)}")
"""
