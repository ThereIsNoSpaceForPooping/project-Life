# -*- coding: utf-8 -*-
"""
Subagent 子图（Supervisor 模式）—— 节点定义

本模块定义 Supervisor-Worker 子图的所有节点与路由函数。

节点清单：
    - supervisor_node       : 中心协调者（LLM 决策下一步 worker）
    - researcher_worker_node: 信息检索 worker
    - coder_worker_node     : 编码 worker
    - analyst_worker_node   : Map-Reduce 分析 worker
    - finalize_node         : 汇总所有 worker 输出为子图出口结果

路由函数：
    - route_after_supervisor: 读取 next_worker，返回下一跳节点名

学习要点：
    - Supervisor 是"中心大脑"，worker 全部回到 Supervisor 等待再次分发，
      直到 Supervisor 输出 FINISH 才进入 finalize。
    - 每个 worker 是"专业执行者"，只负责一类任务，结果回到 Supervisor。
    - 汇总节点（finalize）是图的标准"收口节点"，输出子图对外可见的结果。
"""

import asyncio
from typing import List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agent.shared.llm import get_llm
from app.agent.shared.mapreduce_utils import (
    MAX_CHUNK_CHARS,
    map_summarize_chunk,
    split_text,
)
from app.agent.shared.tool_manager import tool_manager
from app.agent.subagent.state import SubagentState
from app.core.logging import get_logger

logger = get_logger(__name__)


# ============================================================
# 可用 worker 列表（供 Supervisor 的 LLM 知道有哪些选项）
# ============================================================
AVAILABLE_WORKERS = ["researcher", "coder", "analyst", "FINISH"]


# ============================================================
# Supervisor 决策结构化输出
# ============================================================
class SupervisorDecision(BaseModel):
    """
    Supervisor 的分发决策（结构化输出）

    Supervisor 每次调用 LLM 后输出此结构，决定下一步调用哪个 worker 或结束。
    """

    next_worker: str = Field(
        ...,
        description="下一步调用的 worker 名称：researcher / coder / analyst / FINISH",
    )
    reason: str = Field(..., description="决策理由")


# ============================================================
# 节点1：Supervisor（中心协调者）
# ============================================================
async def supervisor_node(state: SubagentState) -> dict:
    """
    Supervisor 节点：中心协调者

    职责：
        1. 分析当前任务和已有 worker 输出。
        2. 决定下一步调用哪个 worker，或判断任务完成（FINISH）。
        3. 防死循环：达到 max_iterations 时强制结束。

    Returns:
        dict: 状态更新字段
            - next_worker : 决策的下一跳 worker
            - subagent_result: 仅在迭代上限场景下写入（直接结束）
            - iteration   : 自增计数器

    学习要点：
        - Supervisor 是 Supervisor 模式的核心，类似团队 leader。
        - 使用 with_structured_output 保证 LLM 输出 JSON 格式。
        - 多轮分发：worker 结果回来后 Supervisor 再次决策。
    """
    logger.info("[Subagent] Supervisor 决策中...")

    query = state.get("query", "")
    worker_outputs = state.get("worker_outputs", [])
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 5)

    # ------------------------------------------------------------------
    # 防御 1：达到最大迭代次数 → 强制结束
    # ------------------------------------------------------------------
    if iteration >= max_iterations:
        logger.warning(
            f"[Subagent] 达到最大迭代次数 {max_iterations}，强制结束"
        )
        return {
            "next_worker": "FINISH",
            "subagent_result": (
                "\n\n".join(worker_outputs)
                if worker_outputs
                else "任务处理完成（达到最大迭代）"
            ),
        }

    # ------------------------------------------------------------------
    # 构造 Supervisor 的 prompt
    # ------------------------------------------------------------------
    outputs_text = (
        "\n\n".join(
            f"【Worker 输出 {i + 1}】\n{out}" for i, out in enumerate(worker_outputs)
        )
        if worker_outputs
        else "（暂无 worker 输出）"
    )

    supervisor_prompt = (
        "你是一个任务协调者（Supervisor），负责把任务分发给专业 worker 执行。\n\n"
        f"用户任务：{query}\n\n"
        f"已有 worker 输出：\n{outputs_text}\n\n"
        "可用 worker：\n"
        "- researcher：信息检索专家，调用 A2A/MCP 工具搜索资料\n"
        "- coder：编码专家，调用 A2A coder 工具编写代码\n"
        "- analyst：分析专家，对长文本进行 Map-Reduce 分析摘要\n"
        "- FINISH：任务已完成，不再需要 worker\n\n"
        "请决定下一步调用哪个 worker。如果已有输出足以回答用户任务，选择 FINISH。"
    )

    llm = get_llm()
    structured_llm = llm.with_structured_output(SupervisorDecision)

    try:
        decision: SupervisorDecision = await structured_llm.ainvoke([
            SystemMessage(content="你是一个任务协调者，负责把任务分发给专业 worker。"),
            HumanMessage(content=supervisor_prompt),
        ])

        logger.info(
            f"[Subagent] Supervisor 决策: next_worker={decision.next_worker}, "
            f"reason={decision.reason}"
        )

        return {
            "next_worker": decision.next_worker,
            "iteration": iteration + 1,
        }
    except Exception as e:
        # ------------------------------------------------------------------
        # 防御 2：LLM 解析失败 → 兜底结束
        # ------------------------------------------------------------------
        logger.error(f"[Subagent] Supervisor 决策失败: {e}，强制结束")
        return {
            "next_worker": "FINISH",
            "subagent_result": (
                "\n\n".join(worker_outputs)
                if worker_outputs
                else "Supervisor 决策失败"
            ),
        }


# ============================================================
# 节点2：Researcher Worker（信息检索专家）
# ============================================================
async def researcher_worker_node(state: SubagentState) -> dict:
    """
    Researcher Worker：信息检索专家

    职责：调用 A2A researcher 工具或 MCP 工具搜索资料；
          若无工具可用，降级为直接用 LLM 回答。

    Returns:
        dict: 状态更新字段
            - worker_outputs: 追加本次输出
            - messages       : 追加一条 AIMessage

    学习要点：
        - Worker 是专业执行者，只负责一类任务。
        - 工具查找采用"name 包含关键词"的模糊匹配，兼容多种命名。
        - 异常降级：工具调用失败时仍要返回可用输出，避免图卡死。
    """
    logger.info("[Subagent] Researcher worker 执行中...")

    query = state.get("query", "")

    try:
        # ------------------------------------------------------------------
        # 在 tool_manager 中查找研究相关工具（模糊匹配 name）
        # ------------------------------------------------------------------
        research_tool = None
        for tool in tool_manager.get_all_tools():
            if "research" in tool.name.lower() or "search" in tool.name.lower():
                research_tool = tool
                break

        if research_tool:
            logger.info(f"[Subagent] Researcher 调用工具: {research_tool.name}")
            result = await research_tool.ainvoke({"query": query})
            output = f"研究结果：{result}"
        else:
            # 降级：直接用 LLM 生成
            logger.info("[Subagent] Researcher 无可用工具，用 LLM 直接回答")
            llm = get_llm()
            response = await llm.ainvoke([
                SystemMessage(content="你是信息检索专家，请根据用户问题提供详细的研究结果。"),
                HumanMessage(content=query),
            ])
            output = f"研究结果：{response.content}"

    except Exception as e:
        # 工具调用失败的降级处理
        logger.error(f"[Subagent] Researcher 执行失败: {e}")
        output = f"研究失败：{e}"

    # ------------------------------------------------------------------
    # 累加 worker 输出（注意：必须读取 + 追加 + 写回，不能用 add_messages 风格）
    # ------------------------------------------------------------------
    worker_outputs = state.get("worker_outputs", [])
    worker_outputs.append(output)

    return {
        "worker_outputs": worker_outputs,
        "messages": [AIMessage(content=output)],
    }


# ============================================================
# 节点3：Coder Worker（编码专家）
# ============================================================
async def coder_worker_node(state: SubagentState) -> dict:
    """
    Coder Worker：编码专家

    职责：调用 A2A coder 工具编写代码；
          若无工具可用，降级为直接用 LLM 生成代码。

    Returns:
        dict: 状态更新字段（worker_outputs + messages）

    学习要点：
        - 同 researcher_worker_node：模糊匹配工具 + 异常降级。
    """
    logger.info("[Subagent] Coder worker 执行中...")

    query = state.get("query", "")

    try:
        # ------------------------------------------------------------------
        # 在 tool_manager 中查找编码相关工具（模糊匹配 name）
        # ------------------------------------------------------------------
        coder_tool = None
        for tool in tool_manager.get_all_tools():
            if "coder" in tool.name.lower() or "code" in tool.name.lower():
                coder_tool = tool
                break

        if coder_tool:
            logger.info(f"[Subagent] Coder 调用工具: {coder_tool.name}")
            result = await coder_tool.ainvoke({"query": query})
            output = f"编码结果：{result}"
        else:
            # 降级：直接用 LLM 生成代码
            logger.info("[Subagent] Coder 无可用工具，用 LLM 直接回答")
            llm = get_llm()
            response = await llm.ainvoke([
                SystemMessage(content="你是编码专家，请根据用户需求提供代码实现。"),
                HumanMessage(content=query),
            ])
            output = f"编码结果：{response.content}"

    except Exception as e:
        # 工具调用失败的降级处理
        logger.error(f"[Subagent] Coder 执行失败: {e}")
        output = f"编码失败：{e}"

    # 累加 worker 输出
    worker_outputs = state.get("worker_outputs", [])
    worker_outputs.append(output)

    return {
        "worker_outputs": worker_outputs,
        "messages": [AIMessage(content=output)],
    }


# ============================================================
# 节点4：Analyst Worker（分析专家，Map-Reduce）
# ============================================================
async def analyst_worker_node(state: SubagentState) -> dict:
    """
    Analyst Worker：分析专家

    职责：对长文本进行 Map-Reduce 分析摘要。
          复用 shared.mapreduce_utils 中的 split_text + map_summarize_chunk。
          单分片场景直接用 LLM 分析，避免不必要的分片开销。

    Returns:
        dict: 状态更新字段（worker_outputs + messages）

    学习要点：
        - Map-Reduce 是处理超长文本的经典模式：先分片（Map）再汇总（Reduce）。
        - 单分片场景是常见短路径，必须有降级分支。
        - 复用 shared 工具函数，保证与 master_graph 行为一致。
    """
    logger.info("[Subagent] Analyst worker 执行中...")

    query = state.get("query", "")
    worker_outputs = state.get("worker_outputs", [])

    # 拼接分析输入：已有 worker 输出 + 用户任务
    analysis_input = query
    if worker_outputs:
        analysis_input = "\n\n".join(worker_outputs) + f"\n\n用户任务：{query}"

    try:
        # ------------------------------------------------------------------
        # 分片 + 并行摘要
        # ------------------------------------------------------------------
        chunks = split_text(analysis_input, MAX_CHUNK_CHARS)

        if len(chunks) <= 1:
            # 单分片直接用 LLM 分析（避免 Map-Reduce 开销）
            llm = get_llm()
            response = await llm.ainvoke([
                SystemMessage(content="你是分析专家，请对以下内容进行深入分析，提取关键信息和结论。"),
                HumanMessage(content=analysis_input),
            ])
            output = f"分析结果：{response.content}"
        else:
            # ------------------------------------------------------------------
            # 多分片：Map（并行摘要）→ Reduce（合并）
            # ------------------------------------------------------------------
            logger.info(f"[Subagent] Analyst 分为 {len(chunks)} 个分片，并行分析")
            chunk_summaries = await asyncio.gather(
                *[map_summarize_chunk(i, chunk, len(chunks)) for i, chunk in enumerate(chunks)]
            )

            # Reduce：把所有分片摘要合并为最终分析报告
            summaries_text = "\n\n".join(
                f"【片段 {i + 1}】\n{s}" for i, s in enumerate(chunk_summaries)
            )
            llm = get_llm()
            reduce_response = await llm.ainvoke([
                HumanMessage(content=f"请合并以下分析摘要为一份连贯的分析报告：\n\n{summaries_text}")
            ])
            output = f"分析结果：{reduce_response.content}"

    except Exception as e:
        # 任何异常都降级为可读错误信息，避免 worker 静默失败
        logger.error(f"[Subagent] Analyst 执行失败: {e}")
        output = f"分析失败：{e}"

    # 累加 worker 输出
    worker_outputs.append(output)

    return {
        "worker_outputs": worker_outputs,
        "messages": [AIMessage(content=output)],
    }


# ============================================================
# 路由：Supervisor 之后的分发
# ============================================================
def route_after_supervisor(state: SubagentState) -> str:
    """
    Supervisor 之后的条件路由

    根据 next_worker 决定调用哪个 worker，或进入 finalize 收口。
    未知 worker 名称会回退到 finalize（避免图卡死）。

    Returns:
        str: 下一跳节点名（researcher / coder / analyst / finalize）
    """
    next_worker = state.get("next_worker", "FINISH")

    if next_worker == "FINISH":
        return "finalize"
    if next_worker == "researcher":
        return "researcher"
    if next_worker == "coder":
        return "coder"
    if next_worker == "analyst":
        return "analyst"

    # 防御：未知 worker → 兜底结束
    logger.warning(f"[Subagent] 未知 worker: {next_worker}，结束")
    return "finalize"


# ============================================================
# 终节点：汇总子图结果
# ============================================================
async def finalize_node(state: SubagentState) -> dict:
    """
    终节点：汇总所有 worker 输出为子图对外可见的结果

    三种收口场景：
        1. Supervisor 因迭代上限强制结束 → subagent_result 已设置，直接返回。
        2. 仅 1 个 worker 输出 → 直接透传，避免不必要的 LLM 调用。
        3. 多个 worker 输出 → 用 LLM 合并为最终结果。

    Returns:
        dict: 状态更新字段（subagent_result）

    学习要点：
        - 多种"结束路径"必须在汇总节点统一处理。
        - 短路径优化（单 worker）能显著降低 token 成本。
    """
    # ------------------------------------------------------------------
    # 场景 1：Supervisor 已写入 subagent_result（迭代上限），透传
    # ------------------------------------------------------------------
    if state.get("subagent_result"):
        return {}

    worker_outputs = state.get("worker_outputs", [])
    query = state.get("query", "")

    # ------------------------------------------------------------------
    # 防御：完全没产出 → 返回可读提示
    # ------------------------------------------------------------------
    if not worker_outputs:
        return {"subagent_result": "子任务未产生任何输出"}

    # ------------------------------------------------------------------
    # 场景 2：仅 1 个 worker 输出 → 直接透传
    # ------------------------------------------------------------------
    if len(worker_outputs) == 1:
        return {"subagent_result": worker_outputs[0]}

    # ------------------------------------------------------------------
    # 场景 3：多个 worker 输出 → LLM 汇总
    # ------------------------------------------------------------------
    outputs_text = "\n\n".join(
        f"【输出 {i + 1}】\n{out}" for i, out in enumerate(worker_outputs)
    )

    llm = get_llm()
    response = await llm.ainvoke([
        SystemMessage(content="你是汇总专家，请把多个 worker 的输出合并为一份连贯的最终结果。"),
        HumanMessage(content=f"用户任务：{query}\n\n各 worker 输出：\n{outputs_text}"),
    ])

    logger.info("[Subagent] Finalize 完成")
    return {"subagent_result": response.content}
