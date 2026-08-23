# -*- coding: utf-8 -*-
"""
统一大图（Master Graph）—— 节点定义

本模块定义统一大图的所有节点、路由函数和辅助工具。

节点清单：
    - guard_input_node           : 输入安全过滤
    - router_node                : 意图路由（含 v3 关键词 → 强制工具 短路）
    - research_subgraph_node     : 研究子图（调用 A2A researcher）
    - mapreduce_node             : Map-Reduce 长文档处理
    - subagent_node              : Supervisor 子图入口（调用 subagent_graph 单例）
    - agent_node                 : Agent 推理（核心，含 v3 force_tool + v4 上下文压缩）
    - human_review_node          : 人机协作
    - reflection_node            : 自我反思
    - guard_output_node          : 输出安全过滤
    - summarizer_node            : 汇总
    - auto_explore_node          : 动态探索（未知意图时使用）

辅助工具：
    - split_text / _map_summarize_chunk : 文本分片 + 并行摘要（内部使用，跨图通过 shared.mapreduce_utils 暴露）
    - compress_messages_if_needed       : 上下文压缩中间件

路由函数：
    - route_after_guard_input / route_after_router / route_after_agent
    - route_after_stuck_guard_wrapper / route_after_human_review
    - route_after_reflection

学习要点：
    - 所有功能作为图中的节点，在一条完整链路中串联。
    - 通过条件路由根据任务类型选择不同路径。
    - 状态中存储所有中间结果，支持时间旅行回溯。
    - 三层防死循环：业务层（stuck_guard）+ 资源层（max_tool_calls）+ 框架层（recursion_limit）。
"""

import asyncio
import json
from typing import List, Optional, Dict, Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from pydantic import BaseModel, Field

from app.agent.a2a.tools_loader import a2a_loader
from app.agent.master.state import MasterState, ReflectionResult, TaskAnalysis
from app.agent.mcp.tools_loader import mcp_loader
from app.agent.middleware.prebuilt_tool_node import PrebuiltToolNode
from app.agent.middleware.stuck_guard import (
    DEFAULT_STUCK_THRESHOLD,
    route_after_stuck_guard,
    stuck_guard_node,
)
from app.agent.shared.llm import get_llm
from app.agent.shared.mapreduce_utils import (
    MAX_CHUNK_CHARS,
    map_summarize_chunk,
    split_text,
)
from app.agent.shared.tool_manager import tool_manager
from app.agent.subagent import subagent_graph
from app.core.logging import get_logger
from app.memory import memory_manager

logger = get_logger(__name__)


# ============================================================
# 关键词 → 强制工具 映射表（v3 新增，v4 扩展 MCP）
# ============================================================
# 作用：当用户 query 命中关键词时，router 在结果中写入 force_tool，
#       agent_node 据此追加 SystemMessage 强制 LLM 调用对应工具。
# 顺序：先匹配先生效（多关键词时取首个命中）。
# 范围：覆盖 a2a_* 全量 Agent + MCP 12 个工具。
# 设计原则：
#   1. 关键词尽量互斥（避免歧义）；歧义时优先匹配更具体的工具。
#   2. file_read 优先于其他文件类工具（用户常说"读 README"）。
#   3. 关键词使用中英双语，方便国内外场景。
FORCE_TOOL_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    # ============= A2A Agent 类 =============
    (("翻译", "translate", "translator"),                 "a2a_translator"),
    (("研究", "调研", "research"),                        "a2a_researcher"),
    (("写代码", "写个程序", "生成代码", "编程"),          "a2a_coder"),
    (("分析", "对比", "analyze", "数据走势"),             "a2a_analyzer"),

    # ============= MCP 工具类（v4 新增） =============
    # 文件操作（注意：file_read 放在 file_write 之前，"读"比"写"更常见）
    (("读文件", "读取", "打开文件", "查看文件", "看下文件", "显示文件", "读一下", "查看", "看看", "read file", "cat "),     "mcp_file_read"),
    (("写文件", "写入文件", "保存文件", "write file"),                                    "mcp_file_write"),
    (("列目录", "列出目录", "查看目录", "ls ", "dir "),                                  "mcp_file_list"),
    (("删除文件", "remove file"),                                                          "mcp_file_delete"),

    # 数据库操作（SELECT 用 db_query，INSERT/UPDATE/DELETE 用 db_execute）
    (("查询表", "select ", "查表", "查询数据", "sql 查询"),                              "mcp_db_query"),
    (("插入数据", "更新数据", "删除数据", "insert ", "update ", "delete from"),         "mcp_db_execute"),
    (("所有表", "有哪些表", "show tables"),                                              "mcp_db_tables"),
    (("表结构", "schema", "表字段"),                                                      "mcp_db_schema"),

    # HTTP 请求
    (("http get", "get 请求", "发起 get"),                                               "mcp_http_get"),
    (("http post", "post 请求", "发起 post", "提交数据"),                                "mcp_http_post"),
    (("http request", "自定义 http", "发请求"),                                          "mcp_http_request"),

    # 代码执行
    (("执行代码", "运行代码", "执行 python", "run code"),                                 "mcp_code_execute"),
    (("计算表达式", "evaluate", "算一下"),                                                "mcp_code_evaluate"),

    # ============= 预留扩展位 =============
    (("搜索知识库", "search_knowledge"),                   "search_knowledge"),
    (("联网搜索", "网上搜", "web_search"),                 "web_search"),
]


def _detect_force_tool(query: str) -> Optional[str]:
    """
    关键词检测：返回首个命中的工具名，未命中返回 None。

    匹配规则：
        - 忽略大小写（query 与关键词统一 lower 后比对）
        - 子串包含即命中（避免 LLM 出现"翻译一下"这种小变化就漏判）

    Args:
        query: 用户原始 query

    Returns:
        命中的工具名（如 a2a_translator / mcp_file_read），未命中返回 None
    """
    if not query:
        return None
    q = query.lower()
    for keywords, tool_name in FORCE_TOOL_KEYWORDS:
        for kw in keywords:
            if kw.lower() in q:
                logger.info(
                    "router 关键词命中: keyword=%r → force_tool=%r (query=%r)",
                    kw, tool_name, query[:60],
                )
                return tool_name
    return None


# ============================================================
# 节点1：输入安全过滤
# ============================================================
def guard_input_node(state: MasterState) -> dict:
    """
    输入安全过滤节点

    检查用户输入是否包含敏感信息、恶意内容等。

    学习要点：
        - 企业级必备：防止注入攻击、敏感信息泄露
        - 可以使用关键词过滤、LLM 分类、正则表达式
        - 不安全时直接返回警告，不继续执行
    """
    logger.info("执行输入安全过滤")

    query = state.get("query", "")
    warnings = []
    is_safe = True

    # 1. 关键词过滤（示例）
    sensitive_keywords = ["密码", "身份证", "银行卡", "secret", "password"]
    for keyword in sensitive_keywords:
        if keyword in query.lower():
            warnings.append(f"检测到敏感关键词: {keyword}")
            is_safe = False

    # 2. 长度检查
    if len(query) > 10000:
        warnings.append("输入过长，可能为恶意攻击")
        is_safe = False

    # 3. SQL 注入检测（示例）
    sql_patterns = ["DROP TABLE", "DELETE FROM", "INSERT INTO", "UNION SELECT"]
    for pattern in sql_patterns:
        if pattern in query.upper():
            warnings.append(f"检测到 SQL 注入模式: {pattern}")
            is_safe = False

    logger.info(f"输入安全检查完成: safe={is_safe}, warnings={warnings}")

    return {
        "input_safe": is_safe,
        "guard_warnings": warnings,
        "messages": [AIMessage(content="输入安全检查完成")] if is_safe else [],
    }


# ============================================================
# 节点2：路由器（意图分类 + 结构化输出）
# ============================================================
def router_node(state: MasterState) -> dict:
    """
    路由器节点

    分析用户意图，决定任务类型和处理路径。
    使用结构化输出确保返回格式正确。

    v3 增强：
        - 在 LLM 分类前先做关键词检测（_detect_force_tool）
        - 命中关键词时，强制设置 force_tool 字段
        - agent_node 读取后追加"必须调用该工具"的 SystemMessage

    学习要点：
        - 使用 with_structured_output 强制返回 JSON
        - 根据任务类型决定后续路由
        - 简单问题直接回答，复杂问题分发到子图
        - 关键词短路：避免 LLM 把"翻译"误判为 simple
    """
    logger.info("执行路由器（意图分类）")

    query = state.get("query", "")

    # ============================================================
    # v3：关键词检测 → 强制工具（在前 LLM 分类之前，避免被覆盖）
    # ============================================================
    force_tool = _detect_force_tool(query)

    # 获取 LLM
    llm = get_llm()

    # 使用结构化输出
    try:
        structured_llm = llm.with_structured_output(TaskAnalysis)

        task_analysis: TaskAnalysis = structured_llm.invoke([
            SystemMessage(content="""你是一个任务分类器。分析用户输入，判断任务类型。

任务类型说明：
- simple: 简单问答，不需要工具或复杂处理
- search: 需要搜索信息、查询数据
- document: 长文档处理、总结、分析
- complex: 复杂任务，需要多步骤协作（研究 + 编码 + 分析）"""),
            HumanMessage(content=query),
        ])

        logger.info(f"任务分析结果: {task_analysis}")

        # 决定路由
        if task_analysis.task_type == "simple":
            next_route = "agent"
        elif task_analysis.task_type == "search":
            next_route = "research_subgraph"
        elif task_analysis.task_type == "document":
            next_route = "mapreduce"
        elif task_analysis.task_type == "complex":
            next_route = "subagent"
        else:
            next_route = "agent"

        # ============================================================
        # v3：关键词命中时把 force_tool 写进 task_analysis & state
        # ============================================================
        # 同时把 requires_tools 置 True，提示 LLM 至少要考虑工具
        analysis_dict = task_analysis.model_dump()
        if force_tool:
            analysis_dict["requires_tools"] = True
            analysis_dict["force_tool"] = force_tool

        return {
            "task_analysis": analysis_dict,
            "next_route": next_route,
            "force_tool": force_tool,  # 顶层 state 字段，供 agent_node 读取
            "messages": [AIMessage(
                content=(
                    f"任务分类: {task_analysis.task_type}"
                    + (f" | 强制工具: {force_tool}" if force_tool else "")
                )
            )],
        }

    except Exception as e:
        # 路由失败 → 默认走简单路径（但保留 force_tool，避免 LLM 异常时丢失强制指令）
        logger.error(f"路由失败: {e}")
        return {
            "task_analysis": {
                "task_type": "simple",
                "priority": "medium",
                "complexity": 5,
                "description": query,
                "requires_tools": bool(force_tool),  # v3：有强制工具时也要 True
                "force_tool": force_tool,
            },
            "next_route": "agent",
            "force_tool": force_tool,
            "messages": [AIMessage(
                content="任务分类失败，使用默认路径"
                + (f" | 强制工具: {force_tool}" if force_tool else "")
            )],
        }


# ============================================================
# 节点3：研究子图
# ============================================================
async def research_subgraph_node(state: MasterState) -> dict:
    """
    研究子图节点

    执行搜索-分析-编译流程。
    调用 A2A researcher agent 进行研究。

    学习要点：
        - 子图作为大图中的一个节点
        - 子图内部可以有多个节点
        - 子图结果返回给大图继续处理
        - 使用 A2A 工具进行真实研究
    """
    logger.info("执行研究子图")

    query = state.get("query", "")

    try:
        # 调用 A2A researcher agent
        logger.info(f"调用 a2a_researcher 研究: {query}")
        if a2a_loader is None or a2a_loader.client is None:
            raise RuntimeError("A2A Loader 未初始化")
        task: Dict[str, Any] = await a2a_loader.client.send(
            text=query,
            agent_name="researcher",
        )
        state_str: str = task.get("status", {}).get("state", "")

        if state_str == "completed":
            # 提取 artifact 中的输出文本
            artifacts: List[Dict[str, Any]] = task.get("artifacts", [])
            if artifacts:
                parts: List[Dict[str, Any]] = artifacts[0].get("parts", [])
                research_content: str = "\n".join(
                    p.get("text", "")
                    for p in parts
                    if p.get("type") == "text"
                )
            else:
                research_content = "研究完成，但未返回具体内容"
            report = f"""
研究报告：{query}

研究结果：
{research_content}
"""
            logger.info("A2A researcher 研究完成")

            return {
                "research_result": report,
                "research_sources": ["a2a_researcher"],
                "messages": [AIMessage(content="研究完成")],
            }
        else:
            logger.warning(f"A2A researcher 返回状态: {state_str}")
            raise Exception(f"A2A 任务未完成: {state_str}")

    except Exception as e:
        # 降级：使用 LLM 直接回答
        logger.error(f"调用 a2a_researcher 失败: {e}，使用 LLM 降级处理")

        llm = get_llm()
        analysis_prompt = f"""请研究并分析以下问题：

用户问题：{query}

请提供详细的研究结果，包括：
1. 关键信息点
2. 相关数据或事实
3. 总结和建议"""

        analysis_response = llm.invoke([HumanMessage(content=analysis_prompt)])

        report = f"""
研究报告：{query}

研究结果：
{analysis_response.content}

（注：A2A researcher 不可用，使用 LLM 直接回答）
"""

        return {
            "research_result": report,
            "research_sources": ["llm_fallback"],
            "messages": [AIMessage(content="研究完成（降级模式）")],
        }


# ============================================================
# 节点4：Map-Reduce
# ============================================================
async def mapreduce_node(state: MasterState) -> dict:
    """
    Map-Reduce 节点（生产级实现）

    处理长文档：按段落分片 → 并行摘要 → 结构化合并。

    优化点：
        - 分片策略：优先按段落（\\n\\n）分割，避免截断句子；段落超长时按句号 fallback
        - 并行 Map：使用 asyncio.gather 并发调用 LLM，n 个分片只需 1 次往返延迟
        - 结构化 prompt：Map 阶段提取关键信息（人物/数据/结论），Reduce 阶段输出结构化总结
        - 输入来源：优先使用 research_result（研究结果可能很长），fallback 到 query

    学习要点：
        - 适合长文档处理（>1000 字）
        - Map 阶段：对每个分片独立处理，互不依赖
        - Reduce 阶段：合并所有结果，消除冗余、保留关键信息
        - 并行化是 Map-Reduce 的核心优势
    """
    logger.info("执行 Map-Reduce")

    # ------------------------------------------------------------------
    # 0. 确定输入文档
    # ------------------------------------------------------------------
    # 优先使用研究结果（A2A researcher 返回的长文本），其次使用用户原始输入
    document = state.get("research_result") or state.get("query", "")
    if not document:
        logger.warning("Map-Reduce 输入为空，跳过")
        return {
            "final_summary": "",
            "messages": [AIMessage(content="Map-Reduce 输入为空")],
        }

    # ------------------------------------------------------------------
    # 1. Split: 按段落分片
    # ------------------------------------------------------------------
    chunks = split_text(document, MAX_CHUNK_CHARS)

    if len(chunks) <= 1:
        # 文档太短，直接用 LLM 生成摘要
        logger.info("文档较短（单分片），直接生成摘要")
        llm = get_llm()
        summary_prompt = (
            f"请总结以下内容的关键信息，包括主要观点、重要数据和结论：\n\n{document}"
        )
        response = llm.invoke([HumanMessage(content=summary_prompt)])
        return {
            "final_summary": response.content,
            "messages": [AIMessage(content="文档摘要生成完成（单分片）")],
        }

    logger.info(f"文档分为 {len(chunks)} 个分片，开始并行 Map")

    # ------------------------------------------------------------------
    # 2. Map: 并行对每个分片生成摘要
    # ------------------------------------------------------------------
    chunk_summaries = await asyncio.gather(
        *[map_summarize_chunk(i, chunk, len(chunks)) for i, chunk in enumerate(chunks)]
    )

    # ------------------------------------------------------------------
    # 3. Reduce: 合并所有摘要为结构化总结
    # ------------------------------------------------------------------
    summaries_text = "\n\n".join(
        f"【分片 {i + 1}】\n{s}" for i, s in enumerate(chunk_summaries)
    )

    reduce_prompt = (
        f"以下是 {len(chunks)} 个分片的摘要，请合并为一份连贯、完整的总结：\n\n"
        f"{summaries_text}\n\n"
        f"要求：\n"
        f"1. 消除分片间的冗余信息\n"
        f"2. 按逻辑顺序组织内容（背景 → 数据 → 结论）\n"
        f"3. 保留所有关键数据和重要观点\n"
        f"4. 输出格式：概述 + 关键要点列表 + 总结"
    )

    llm = get_llm()
    reduce_response = await llm.ainvoke([HumanMessage(content=reduce_prompt)])

    logger.info(f"Map-Reduce 完成（{len(chunks)} 个分片 → 1 份总结）")

    return {
        "final_summary": reduce_response.content,
        "messages": [AIMessage(content="Map-Reduce 处理完成")],
    }


# ============================================================
# 节点5：Subagent（Supervisor 子图）
# ============================================================
async def subagent_node(state: MasterState) -> dict:
    """
    Subagent 节点：调用 Supervisor 子图处理复杂任务

    流程：
        1. 从 MasterState 提取 query，构造子图输入
        2. 调用编译后的子图（Supervisor 模式：分发 → worker → 汇总）
        3. 把子图结果写回 MasterState.subagent_result

    学习要点：
        - 子图作为节点：master_graph 把整个子图当作一个节点调用
        - 状态映射：入口把 MasterState 字段映射到 SubagentState，出口反向映射
        - Supervisor 模式：中心协调 + 专业 worker，支持多轮分发
        - subagent_graph 使用模块级单例，避免每次请求重新编译
    """
    logger.info("执行 Subagent 子图（Supervisor 模式）")

    query = state.get("query", "")
    if not query:
        logger.warning("Subagent 输入为空，跳过")
        return {
            "subagent_result": "",
            "messages": [AIMessage(content="Subagent 输入为空")],
        }

    # 构造子图输入
    subagent_input = {
        "messages": [HumanMessage(content=query)],
        "query": query,
        "next_worker": None,
        "worker_outputs": [],
        "subagent_result": None,
        "iteration": 0,
        "max_iterations": 5,
    }

    try:
        # 调用子图单例（来自 app.agent.subagent 模块）
        result = await subagent_graph.ainvoke(subagent_input)

        subagent_result = result.get("subagent_result", "")
        logger.info(f"Subagent 完成，结果长度: {len(subagent_result)}")

        return {
            "subagent_result": subagent_result,
            "messages": [AIMessage(content=f"Subagent 处理完成：{subagent_result[:200]}...")],
        }
    except Exception as e:
        logger.error(f"Subagent 执行失败: {e}")
        return {
            "subagent_result": f"子任务执行失败：{e}",
            "messages": [AIMessage(content=f"Subagent 执行失败：{e}")],
        }


# ============================================================
# 上下文压缩中间件（方案 A：所有 LLM 调用点前的自适应检测）
# ============================================================

# 触发压缩的字符数阈值（约 4000 tokens，预留输出空间）
MAX_CONTEXT_CHARS = 12000
# 压缩时保留的近期消息条数（保留最新对话上下文）
KEEP_RECENT_MESSAGES = 6


async def compress_messages_if_needed(messages: List[BaseMessage]) -> List[BaseMessage]:
    """
    上下文压缩中间件：检测 messages 总长度，超阈值时用 Map-Reduce 摘要替换中段消息。

    策略：
        [首条用户消息] + [中段消息的 Map-Reduce 摘要] + [最近 N 条消息]

    触发条件：
        messages 总字符数 > MAX_CONTEXT_CHARS 且消息数 > KEEP_RECENT_MESSAGES + 2

    Args:
        messages: 待检测的消息列表

    Returns:
        压缩后的消息列表（未超阈值则原样返回）

    学习要点：
        - 上下文窗口是 LLM 的硬约束，必须有兜底压缩策略。
        - 保留首条 + 最近 N 条，可维持对话连贯性。
        - 中段使用 Map-Reduce 摘要，兼顾压缩率与信息保留。
    """
    # 计算总字符数
    total_chars = sum(len(m.content) if isinstance(m.content, str) else 0 for m in messages)

    if total_chars <= MAX_CONTEXT_CHARS:
        return messages

    # 消息太少，无法压缩
    if len(messages) <= KEEP_RECENT_MESSAGES + 2:
        return messages

    logger.info(
        f"上下文压缩触发：总字符数 {total_chars} > {MAX_CONTEXT_CHARS}，"
        f"消息数 {len(messages)}"
    )

    # 分割：首条 + 中段 + 最近 N 条
    first_msg = messages[0]
    recent_msgs = messages[-KEEP_RECENT_MESSAGES:]
    middle_msgs = messages[1:-KEEP_RECENT_MESSAGES]

    # 把中段消息拼接为文本，用 Map-Reduce 压缩
    middle_text = "\n\n".join(
        f"[{m.__class__.__name__}] {m.content}"
        for m in middle_msgs
        if isinstance(m.content, str) and m.content.strip()
    )

    if not middle_text.strip():
        return messages

    # 分片 + 并行摘要
    chunks = split_text(middle_text, MAX_CHUNK_CHARS)
    if len(chunks) <= 1:
        # 单分片直接摘要
        llm = get_llm()
        response = await llm.ainvoke([
            HumanMessage(content=f"请总结以下对话历史的关键信息：\n\n{middle_text}")
        ])
        summary = response.content
    else:
        logger.info(f"中段消息分为 {len(chunks)} 个分片，并行压缩")
        chunk_summaries = await asyncio.gather(
            *[map_summarize_chunk(i, chunk, len(chunks)) for i, chunk in enumerate(chunks)]
        )
        # Reduce 合并
        summaries_text = "\n\n".join(
            f"【片段 {i + 1}】\n{s}" for i, s in enumerate(chunk_summaries)
        )
        llm = get_llm()
        reduce_response = await llm.ainvoke([
            HumanMessage(content=f"请合并以下摘要为一份连贯的对话历史总结：\n\n{summaries_text}")
        ])
        summary = reduce_response.content

    # 重组：首条 + 摘要 SystemMessage + 最近 N 条
    compressed = [
        first_msg,
        SystemMessage(content=f"[历史对话摘要]\n{summary}"),
        *recent_msgs,
    ]

    new_chars = sum(len(m.content) if isinstance(m.content, str) else 0 for m in compressed)
    logger.info(
        f"上下文压缩完成：{total_chars} → {new_chars} 字符 "
        f"({len(messages)} → {len(compressed)} 条消息)"
    )

    return compressed


# ============================================================
# 节点6：Agent 推理
# ============================================================
async def agent_node(state: MasterState) -> dict:
    """
    Agent 推理节点

    调用 LLM 进行推理，可能产生工具调用。

    学习要点：
        - 这是核心推理节点
        - 根据状态决定是否需要工具
        - 支持多轮对话
        - 通过 SystemMessage 显式提示"一次性工具用完即止"，减少死循环

    v3 增强：
        - 读取 router 注入的 force_tool，追加"必须调用该工具"的 SystemMessage
        - 优先级最高（最后追加），确保 LLM 在最终决策时能看到

    v4 增强：
        - 调用 LLM 前自动检测上下文长度，超阈值时用 Map-Reduce 摘要压缩历史消息
        - 避免长对话或长研究结果导致上下文溢出
    """
    logger.info("执行 Agent 推理")

    messages = state.get("messages", [])
    query = state.get("query", "")

    # 如果有研究结果，加入上下文
    research_result = state.get("research_result")
    if research_result:
        messages = messages + [SystemMessage(content=f"研究结果：{research_result}")]

    # 如果有 Map-Reduce 结果
    final_summary = state.get("final_summary")
    if final_summary:
        messages = messages + [SystemMessage(content=f"文档摘要：{final_summary}")]

    # 如果有 Subagent 子图结果
    subagent_result = state.get("subagent_result")
    if subagent_result:
        messages = messages + [SystemMessage(content=f"子任务结果：{subagent_result}")]

    # ============================================================
    # 反死循环引导（生产级关键）
    # ============================================================
    # 现象：LLM 拿到工具结果后仍反复调用同一工具（如 a2a_translator）
    # 策略：在 tools 节点之后追加一条 SystemMessage，引导 LLM 基于结果收尾
    # 注意：仅在已有 tool_call 计数 >0 时追加，避免首次推理时被误导
    if state.get("tool_call_count", 0) > 0:
        guidance = (
            "系统提示：你已经调用过工具并收到结果。"
            "如果结果已经包含用户所需信息，请直接基于结果用自然语言回答用户，"
            "不要再次调用同一工具。仅在确实需要补充新信息时才发起新的工具调用，"
            "且新调用的参数应与之前不同。"
        )
        messages = messages + [SystemMessage(content=guidance)]

    # ============================================================
    # v3：强制工具调用指令（关键词路由触发）
    # ============================================================
    # 触发条件：router_node 命中关键词后注入了 force_tool
    # 作用：追加在 messages 末尾，优先级最高，强制 LLM 调用目标工具
    # 配合：stuck_guard 在工具结果回来后会追加"已收尾"指令，避免死循环
    force_tool = state.get("force_tool")
    if force_tool:
        must_call = (
            f"系统强制指令（v3）：检测到用户任务「{query}」命中关键词路由，"
            f"必须通过调用 `{force_tool}` 工具完成本次任务。\n"
            f"要求：\n"
            f"  1. 在本次响应中必须发起对 `{force_tool}` 的工具调用（不要跳过工具直接回答）；\n"
            f"  2. 工具调用完成后，基于返回结果用自然语言向用户呈现最终答案；\n"
            f"  3. 不要重复调用相同工具（同一 (tool_name, args) 组合最多调用 1 次）。"
        )
        messages = messages + [SystemMessage(content=must_call)]
        logger.info(f"Agent 注入强制工具指令: force_tool={force_tool}")

    # 获取 LLM，绑定所有可用工具（本地 + MCP 动态工具）
    llm = get_llm()
    llm_with_tools = llm.bind_tools(tool_manager.get_all_tools())

    # v4：上下文压缩（超阈值时用 Map-Reduce 摘要替换中段历史消息）
    messages = await compress_messages_if_needed(messages)

    # 调用 LLM
    logger.info(f"Agent 输入消息数: {len(messages)}")
    response = await llm_with_tools.ainvoke(messages)

    logger.info(f"Agent 推理完成，工具调用: {len(response.tool_calls)}")

    # 打印 Agent 推理内容
    if response.content:
        logger.info(f"Agent 推理内容: {response.content[:500]}")

    # 打印工具调用详情
    if response.tool_calls:
        for i, tc in enumerate(response.tool_calls):
            logger.info(f"  工具调用[{i+1}]: name={tc['name']}, args={tc['args']}")

    return {
        "messages": [response],
    }


# ============================================================
# 节点7：人机协作
# ============================================================
def human_review_node(state: MasterState) -> dict:
    """
    人机协作节点

    敏感操作前暂停，等待人工确认。

    学习要点：
        - 企业级必备：关键操作需要人工审核
        - 可以配置哪些操作需要审核
        - 暂停/恢复机制
    """
    logger.info("执行人机协作审核")

    messages = state.get("messages", [])
    last_message = messages[-1] if messages else None
    if last_message is None:
        return {"approved": True}

    # 检查是否有工具调用需要审核
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        pending_action = f"即将执行工具: {', '.join([tc['name'] for tc in last_message.tool_calls])}"

        # 这里简化处理，实际应该使用 interrupt 机制
        # 模拟人工确认（总是批准）
        approved = True
        human_feedback = "批准执行"

        logger.info(f"人工审核: {pending_action}, approved={approved}")

        # 注意：不要往 messages 里追加 AIMessage！
        # 原因：PrebuiltToolNode._find_last_ai() 会找到最后一条 AIMessage，
        # 如果这里追加一条没有 tool_calls 的 AIMessage，
        # 会导致 tools 节点找不到原始的 tool_calls，工具无法执行。
        return {
            "pending_action": pending_action,
            "approved": approved,
            "human_feedback": human_feedback,
        }

    # 无需审核时，也不修改 messages
    return {
        "approved": True,
    }


# ============================================================
# 节点8：自我反思
# ============================================================
async def reflection_node(state: MasterState) -> dict:
    """
    自我反思节点

    Agent 执行后自我评估，不满意则重试。

    学习要点：
        - 提高输出质量
        - 减少幻觉
        - 可以设置最大重试次数
    """
    logger.info("执行自我反思")

    messages = state.get("messages", [])
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)

    if retry_count >= max_retries:
        logger.info("达到最大重试次数，跳过反思")
        return {
            "reflection": {"is_satisfactory": True, "confidence": 1.0},
            "messages": [AIMessage(content="达到最大重试次数")],
        }

    # 获取最后一条 AI 消息
    ai_messages = [m for m in messages if isinstance(m, AIMessage)]
    if not ai_messages:
        return {
            "reflection": {"is_satisfactory": True, "confidence": 1.0},
            "messages": [],
        }

    last_response = ai_messages[-1].content

    # 使用 LLM 进行反思
    llm = get_llm()

    try:
        structured_llm = llm.with_structured_output(ReflectionResult)

        reflection: ReflectionResult = await structured_llm.ainvoke([
            SystemMessage(content="你是一个质量评估专家。评估 AI 的回答是否准确、完整、有用。"),
            HumanMessage(content=f"请评估以下回答：{last_response}"),
        ])

        logger.info(
            f"反思结果: satisfactory={reflection.is_satisfactory}, "
            f"confidence={reflection.confidence}"
        )

        return {
            "reflection": reflection.model_dump(),
            "retry_count": retry_count + 1 if not reflection.is_satisfactory else retry_count,
            "messages": [AIMessage(content=f"反思完成: 满意度={reflection.is_satisfactory}")],
        }

    except Exception as e:
        # 反思失败 → 兜底为"满意"，避免流程中断
        logger.error(f"反思失败: {e}")
        return {
            "reflection": {"is_satisfactory": True, "confidence": 0.5},
            "messages": [AIMessage(content="反思失败，继续执行")],
        }


# ============================================================
# 节点9：输出安全过滤
# ============================================================
def guard_output_node(state: MasterState) -> dict:
    """
    输出安全过滤节点

    检查 AI 输出是否包含敏感信息。

    学习要点：
        - 防止泄露系统提示词、内部信息
        - 过滤不当内容
        - 合规检查
    """
    logger.info("执行输出安全过滤")

    messages = state.get("messages", [])
    ai_messages = [m for m in messages if isinstance(m, AIMessage)]

    if not ai_messages:
        return {"output_safe": True}

    last_response = ai_messages[-1].content
    warnings = []
    is_safe = True

    # 检查敏感信息
    sensitive_patterns = ["API_KEY", "SECRET", "PASSWORD", "私钥"]
    for pattern in sensitive_patterns:
        if pattern in last_response.upper():
            warnings.append(f"输出包含敏感信息: {pattern}")
            is_safe = False

    logger.info(f"输出安全检查完成: safe={is_safe}")

    return {
        "output_safe": is_safe,
        "guard_warnings": state.get("guard_warnings", []) + warnings,
    }


# ============================================================
# 节点10：汇总节点
# ============================================================
def summarizer_node(state: MasterState) -> dict:
    """
    汇总节点

    整合所有处理结果，生成最终响应。

    学习要点：
        - 整合多来源信息
        - 生成连贯的最终回答
        - 含 final_response 兜底：极端情况下 LLM 因工具循环未给出文本时，
          自动从最后一条 ToolMessage 提取答案，避免前端拿到 None
    """
    logger.info("执行汇总")

    # 收集所有结果
    results = []

    if state.get("research_result"):
        results.append(f"研究结果: {state['research_result']}")

    if state.get("final_summary"):
        results.append(f"文档摘要: {state['final_summary']}")

    if state.get("subagent_result"):
        results.append(f"子任务结果: {state['subagent_result']}")

    # 获取最后的 AI 响应
    messages = state.get("messages", [])
    ai_messages = [m for m in messages if isinstance(m, AIMessage)]
    if ai_messages:
        results.append(f"AI 回答: {ai_messages[-1].content}")

    # 整合
    if results:
        final_response = "\n\n".join(results)
    else:
        # ============================================================
        # 兜底分支（生产级关键）：results 为空时的安全降级
        # ============================================================
        # 触发场景：路由路径完全跳过了所有"产生 results"的节点
        # 安全策略：直接读最后一条 ToolMessage 的 content 作为最终回答
        last_tool_message: Optional[ToolMessage] = None
        for msg in reversed(messages):
            if isinstance(msg, ToolMessage):
                last_tool_message = msg
                break

        if last_tool_message is not None and last_tool_message.content:
            final_response = f"（自动汇总工具结果）{last_tool_message.content}"
        else:
            final_response = "处理完成，但未生成有效结果。"

    logger.info("汇总完成")

    return {
        "final_response": final_response,
        "messages": [AIMessage(content=final_response)],
    }


# ============================================================
# 节点：动态探索（未知意图时使用）
# ============================================================
async def auto_explore_node(state: MasterState) -> dict:
    """
    动态探索节点（未知意图时使用）

    当路由器无法分类任务时，动态获取 MCP 和 A2A 的能力列表，
    让 LLM 自主选择使用哪些工具/Agent。

    学习要点：
        - 动态发现：先获取能力列表，再选择调用
        - 与硬编码方式对比：更灵活，但多一次请求
        - 适用于：未知意图、新任务类型、能力经常变化的场景
    """
    logger.info("执行动态探索（未知意图）")

    query = state.get("query", "")

    # ------------------------------------------------------------------
    # 1. 动态获取 MCP 工具列表
    # ------------------------------------------------------------------
    mcp_tools: List[Dict[str, Any]] = []
    try:
        if mcp_loader is not None and mcp_loader.client is not None:
            mcp_tools = await mcp_loader.client.list_tools()
            logger.info(f"获取到 {len(mcp_tools)} 个 MCP 工具")
        else:
            logger.warning("MCP Loader 未初始化")
    except Exception as e:
        logger.error(f"获取 MCP 工具失败: {e}")

    # ------------------------------------------------------------------
    # 2. 动态获取 A2A Agent 列表
    # ------------------------------------------------------------------
    a2a_agents: List[Dict[str, Any]] = []
    try:
        if a2a_loader is not None and a2a_loader.client is not None:
            if a2a_loader.client.agent_card is None:
                await a2a_loader.client.discover()
            card: Optional[Dict[str, Any]] = a2a_loader.client.agent_card
            if card:
                # 从 AgentCard 的 skills 构造 agents 列表
                seen: set = set()
                for skill in card.get("skills", []):
                    skill_id: str = skill.get("id", "")
                    agent_name: str = skill_id.split("-")[0] if "-" in skill_id else skill_id
                    if agent_name and agent_name not in seen:
                        a2a_agents.append({
                            "name": agent_name,
                            "description": skill.get("description", ""),
                        })
                        seen.add(agent_name)
            logger.info(f"获取到 {len(a2a_agents)} 个 A2A Agent")
        else:
            logger.warning("A2A Loader 未初始化")
    except Exception as e:
        logger.error(f"获取 A2A Agent 列表失败: {e}")

    # ------------------------------------------------------------------
    # 3. 构建能力描述
    # ------------------------------------------------------------------
    capabilities_desc = "可用能力：\n\n"

    if mcp_tools:
        capabilities_desc += "【MCP 工具】\n"
        for tool in mcp_tools:
            capabilities_desc += f"- {tool['name']}: {tool.get('description', '无描述')}\n"
        capabilities_desc += "\n"

    if a2a_agents:
        capabilities_desc += "【A2A Agent】\n"
        for agent in a2a_agents:
            capabilities_desc += f"- {agent['name']}: {agent.get('description', '无描述')}\n"
        capabilities_desc += "\n"

    if not mcp_tools and not a2a_agents:
        capabilities_desc += "无可用外部能力\n"

    # ------------------------------------------------------------------
    # 4. LLM 自主选择使用哪些能力
    # ------------------------------------------------------------------
    llm = get_llm()

    class CapabilitySelection(BaseModel):
        """能力选择结果"""
        selected_mcp_tools: List[str] = Field(default_factory=list, description="选中的 MCP 工具名")
        selected_a2a_agents: List[str] = Field(default_factory=list, description="选中的 A2A Agent 名")
        reason: str = Field(..., description="选择理由")

    structured_llm = llm.with_structured_output(CapabilitySelection)

    selection = structured_llm.invoke([
        SystemMessage(content=f"""你是一个能力选择器。根据用户问题和可用能力，选择合适的工具/Agent。

{capabilities_desc}

选择原则：
- 如果需要文件/数据库/HTTP/代码操作 → 选择 MCP 工具
- 如果需要研究/编码/翻译/分析 → 选择 A2A Agent
- 可以不选择任何能力，直接回答
- 选择最相关的 1-3 个能力"""),
        HumanMessage(content=query),
    ])

    logger.info(f"能力选择结果: {selection}")

    # ------------------------------------------------------------------
    # 5. 执行选定的能力
    # ------------------------------------------------------------------
    results = []

    # 执行 MCP 工具
    for tool_name in selection.selected_mcp_tools:
        try:
            # 根据工具类型构造参数
            args: Dict[str, Any] = {}
            if "file" in tool_name:
                args = {"path": "example.txt"}
            elif "db" in tool_name:
                args = {"sql": "SELECT 1"}
            elif "http" in tool_name:
                args = {"url": "https://httpbin.org/get"}
            elif "code" in tool_name:
                args = {"code": "print('hello')"}

            if mcp_loader is None or mcp_loader.client is None:
                raise RuntimeError("MCP Loader 未初始化")
            mcp_result: Dict[str, Any] = await mcp_loader.client.call_tool(tool_name, args)
            # 解析 content 列表
            content_text: str = "\n".join(
                item.get("text", "")
                for item in mcp_result.get("content", [])
                if item.get("type") == "text"
            )
            results.append({
                "type": "mcp",
                "tool": tool_name,
                "result": content_text or mcp_result,
            })
            logger.info(f"MCP 工具 {tool_name} 执行完成")
        except Exception as e:
            logger.error(f"MCP 工具 {tool_name} 执行失败: {e}")
            results.append({
                "type": "mcp",
                "tool": tool_name,
                "error": str(e),
            })

    # 执行 A2A Agent
    for agent_name in selection.selected_a2a_agents:
        try:
            if a2a_loader is None or a2a_loader.client is None:
                raise RuntimeError("A2A Loader 未初始化")
            a2a_task: Dict[str, Any] = await a2a_loader.client.send(
                text=query,
                agent_name=agent_name,
            )
            # 提取 artifact 中的输出
            artifacts_list: List[Dict[str, Any]] = a2a_task.get("artifacts", [])
            output_text: str = ""
            if artifacts_list:
                parts_list: List[Dict[str, Any]] = artifacts_list[0].get("parts", [])
                output_text = "\n".join(
                    p.get("text", "")
                    for p in parts_list
                    if p.get("type") == "text"
                )
            results.append({
                "type": "a2a",
                "agent": agent_name,
                "result": output_text or a2a_task,
            })
            logger.info(f"A2A Agent {agent_name} 执行完成")
        except Exception as e:
            logger.error(f"A2A Agent {agent_name} 执行失败: {e}")
            results.append({
                "type": "a2a",
                "agent": agent_name,
                "error": str(e),
            })

    # ------------------------------------------------------------------
    # 6. 汇总结果
    # ------------------------------------------------------------------
    summary_parts = []
    for r in results:
        if r.get("error"):
            summary_parts.append(
                f"[{r['type']}] {r.get('tool') or r.get('agent')}: 错误 - {r['error']}"
            )
        else:
            summary_parts.append(
                f"[{r['type']}] {r.get('tool') or r.get('agent')}: 成功"
            )

    summary = "\n".join(summary_parts) if summary_parts else "未执行任何外部能力"

    logger.info("动态探索完成")

    return {
        "messages": [AIMessage(content=f"动态探索完成:\n{summary}")],
    }


# ============================================================
# 路由函数
# ============================================================
def route_after_guard_input(state: MasterState) -> str:
    """
    输入安全检查后的路由

    决策：
        - 不安全 → summarizer（直接进入收口，结束流程）
        - 安全   → router
    """
    if not state.get("input_safe", True):
        return "summarizer"
    return "router"


def route_after_router(state: MasterState) -> str:
    """
    路由器后的路由

    读取 next_route 字段，决定下一跳节点。
    """
    return state.get("next_route", "agent")


def route_after_agent(state: MasterState) -> str:
    """
    Agent 推理后的路由（v2 —— 防死循环重构）

    决策：
        - 有 tool_calls → stuck_guard（防抖守卫）
        - 无 tool_calls → reflection
    """
    messages = state.get("messages", [])
    if not messages:
        return "reflection"

    last_message = messages[-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "stuck_guard"
    return "reflection"


def route_after_stuck_guard_wrapper(state: MasterState) -> str:
    """
    stuck_guard 节点之后的路由（薄包装，复用 middleware 中的纯函数）

    决策：
        - _force_skip_tools=True → reflection（强制跳过 tools）
        - 否则 → human_review
    """
    return route_after_stuck_guard(state)


def route_after_human_review(state: MasterState) -> str:
    """
    人工审核后的路由（v2）

    决策：
        - 未批准 → reflection
        - 已批准但达到 max_tool_calls → reflection（兜底，stuck_guard 已先拦截）
        - 已批准且未达上限 → tools
    """
    approved = state.get("approved", False)
    tool_call_count = state.get("tool_call_count", 0)
    max_tool_calls = state.get("max_tool_calls", 5)
    force_skip = state.get("_force_skip_tools", False)

    logger.info(
        f"[ROUTE-DEBUG] route_after_human_review: "
        f"approved={approved}, tool_call_count={tool_call_count}, "
        f"max_tool_calls={max_tool_calls}, _force_skip_tools={force_skip}"
    )

    if not approved:
        logger.info("[ROUTE-DEBUG] → reflection (未批准)")
        return "reflection"

    if tool_call_count >= max_tool_calls:
        logger.warning(
            f"工具调用次数已达上限 ({max_tool_calls})，强制结束"
        )
        logger.info("[ROUTE-DEBUG] → reflection (达到上限)")
        return "reflection"

    logger.info("[ROUTE-DEBUG] → tools (已批准，进入工具执行)")
    return "tools"


def route_after_reflection(state: MasterState) -> str:
    """
    反思后的路由

    决策：
        - 满意或达到最大重试 → guard_output
        - 不满意 → agent（重试）
    """
    reflection = state.get("reflection", {})
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)

    if reflection.get("is_satisfactory", True) or retry_count >= max_retries:
        return "guard_output"
    return "agent"


# ============================================================
# 节点包装器
# ============================================================
def _stuck_guard_node_wrapper(state: MasterState) -> dict:
    """
    stuck_guard_node 的薄包装，使其能直接接 LangGraph StateGraph。

    复用 middleware.stuck_guard.stuck_guard_node 纯函数，保证逻辑可单测。
    """
    return stuck_guard_node(state, threshold=DEFAULT_STUCK_THRESHOLD)


def _build_prebuilt_tool_node() -> PrebuiltToolNode:
    """
    构造"prebuilt 风格"工具执行节点。

    行为：
        - 接收 tool_manager 中所有工具（本地 + MCP + A2A）
        - 自动区分同步/异步工具
        - 工具异常时不抛错，封装为 ToolMessage.content 返回
    """
    return PrebuiltToolNode(
        tools=tool_manager.get_all_tools(),
        handle_tool_errors=True,  # 生产环境：异常不中断流程
    )
