# -*- coding: utf-8 -*-
"""
统一大图（Master Graph）

将所有高级功能集成到一个完整的任务处理流程中：
- 安全护栏（Guard Rails）
- 结构化输出（Structured Output）
- 子图（Subgraph）
- Map-Reduce
- 并行执行（Fan-out/Fan-in）
- 动态工具选择
- MCP 工具调用
- 人机协作（Interrupt）
- 自我反思（Reflection）
- 时间旅行（Time Travel）

学习要点：
- 所有功能作为图中的节点，在一条完整链路中串联
- 通过条件路由根据任务类型选择不同路径
- 状态中存储所有中间结果，支持时间旅行回溯
"""

import json
from typing import List, Optional, Dict, Any, Annotated
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from app.agent.nodes import get_llm, tool_manager
from app.memory import memory_manager
from app.core.config import settings
from app.core.logging import get_logger
from app.agent.mcp.simple_client import mcp_client
from app.agent.a2a.simple_client import a2a_client

# 中间件：自研的"prebuilt 风格"工具节点 + 重复调用守卫
# 说明：官方 langgraph.prebuilt.ToolNode 在当前 langgraph==1.1.3 + langchain-core==0.3.63
#       组合下存在 ImportError，故采用自研兼容实现（接口与官方对齐，未来可一行替换）。
from app.agent.middleware.prebuilt_tool_node import PrebuiltToolNode, tools_condition
from app.agent.middleware.stuck_guard import (
    stuck_guard_node,
    route_after_stuck_guard,
    DEFAULT_STUCK_THRESHOLD,
)

logger = get_logger(__name__)


# ============================================================
# 结构化输出模型
# ============================================================

class TaskAnalysis(BaseModel):
    """任务分析结果（路由器使用）"""
    task_type: str = Field(..., description="任务类型：simple/search/document/parallel/unknown")
    priority: str = Field(..., description="优先级：high/medium/low")
    complexity: int = Field(..., ge=1, le=10, description="复杂度 1-10")
    description: str = Field(..., description="任务描述")
    requires_tools: bool = Field(default=False, description="是否需要工具")


class ReflectionResult(BaseModel):
    """自我反思结果"""
    is_satisfactory: bool = Field(..., description="是否满意")
    confidence: float = Field(..., ge=0, le=1, description="置信度")
    issues: List[str] = Field(default_factory=list, description="发现的问题")
    suggestions: str = Field(default="", description="改进建议")


# ============================================================
# 统一状态定义
# ============================================================

class MasterState(TypedDict):
    """
    统一大图状态
    
    包含所有功能模块所需的字段，支持完整任务链路。
    """
    # 消息历史（LangGraph 自动追加）
    messages: Annotated[List[BaseMessage], add_messages]
    
    # 基础信息
    query: str                          # 用户原始输入
    conversation_id: str                # 对话ID
    
    # 安全护栏
    input_safe: bool                    # 输入是否安全
    output_safe: bool                   # 输出是否安全
    guard_warnings: List[str]           # 安全警告
    
    # 路由决策
    task_analysis: Optional[dict]       # 任务分析结果
    next_route: Optional[str]           # 下一个路由
    
    # 子图结果
    research_result: Optional[str]      # 研究结果
    research_sources: List[str]         # 研究来源
    
    # Map-Reduce 结果
    document: Optional[str]             # 原始文档
    chunks: List[str]                   # 文档分片
    chunk_summaries: List[str]          # 分片摘要
    final_summary: Optional[str]        # 最终摘要
    
    # 并行执行结果
    parallel_tasks: List[Dict]          # 并行任务列表
    worker_results: List[Dict]          # Worker 结果
    aggregated_result: Optional[str]    # 聚合结果
    
    # 动态工具
    selected_tools: List[str]           # 选中的工具名
    tool_results: Dict[str, Any]        # 工具执行结果
    
    # MCP 工具
    mcp_tool_calls: List[Dict]          # MCP 工具调用
    mcp_results: List[Dict]             # MCP 结果
    # 注：原 mcp_executed 字段已移除。死循环防护由 stuck_guard + max_tool_calls +
    #     recursion_limit 三层共同负责，标记位已无存在必要。

    # A2A 协作
    a2a_task_id: Optional[str]          # A2A 任务 ID
    a2a_result: Optional[Dict]          # A2A 结果
    # 注：原 a2a_executed 字段已移除（理由同上）。

    # 人机协作
    pending_action: Optional[str]       # 待确认操作
    human_feedback: Optional[str]       # 人工反馈
    approved: bool                      # 是否批准
    
    # 自我反思
    reflection: Optional[dict]          # 反思结果
    retry_count: int                    # 重试次数
    max_retries: int                    # 最大重试次数
    
    # 工具调用控制
    tool_call_count: int                # 工具调用次数（防止死循环）
    max_tool_calls: int                 # 最大工具调用次数
    
    # 重复调用守卫（防抖）—— 详见 app.agent.middleware.stuck_guard
    stuck_signature: Optional[str]      # 最近一次工具调用的稳定签名
    stuck_count: int                    # 连续相同签名的累计次数
    _force_skip_tools: bool             # 内部标记：stuck_guard 判定后是否强制跳过 tools 节点

    # 强制工具路由（v3 —— 关键词触发）
    # 说明：router_node 检测到特定关键词时强制注入目标工具名，
    #       agent_node 读取后追加"必须调用该工具"的 SystemMessage，避免
    #       LLM 自行判断"翻译是简单任务"而跳过工具调用。
    force_tool: Optional[str]           # router 注入：强制 agent 调用的工具名（如 a2a_translator）
    
    # 最终输出
    final_response: Optional[str]       # 最终响应


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
        "messages": [AIMessage(content="输入安全检查完成")] if is_safe else []
    }


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
- parallel: 需要并行处理多个独立任务"""),
            HumanMessage(content=query)
        ])

        logger.info(f"任务分析结果: {task_analysis}")

        # 决定路由
        if task_analysis.task_type == "simple":
            next_route = "agent"
        elif task_analysis.task_type == "search":
            next_route = "research_subgraph"
        elif task_analysis.task_type == "document":
            next_route = "mapreduce"
        elif task_analysis.task_type == "parallel":
            next_route = "parallel"
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
        logger.error(f"路由失败: {e}")
        # 默认走简单路径（但保留 force_tool，避免 LLM 异常时丢失强制指令）
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
        result = await a2a_client.create_task(
            agent_name="researcher",
            input_data={"query": query}
        )
        
        if result.get("status") == "completed":
            research_content = result.get("result", {}).get("output", "研究完成，但未返回具体内容")
            report = f"""
研究报告：{query}

研究结果：
{research_content}
"""
            logger.info("A2A researcher 研究完成")
            
            return {
                "research_result": report,
                "research_sources": ["a2a_researcher"],
                "messages": [AIMessage(content="研究完成")]
            }
        else:
            logger.warning(f"A2A researcher 返回状态: {result.get('status')}")
            raise Exception(f"A2A 任务未完成: {result.get('status')}")
            
    except Exception as e:
        logger.error(f"调用 a2a_researcher 失败: {e}，使用 LLM 降级处理")
        
        # 降级：使用 LLM 直接回答
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
            "messages": [AIMessage(content="研究完成（降级模式）")]
        }


# ============================================================
# 节点4：Map-Reduce
# ============================================================

def mapreduce_node(state: MasterState) -> dict:
    """
    Map-Reduce 节点
    
    处理长文档：分片 → 并行摘要 → 合并。
    
    学习要点：
    - 适合长文档处理
    - Map 阶段：对每个分片独立处理
    - Reduce 阶段：合并所有结果
    """
    logger.info("执行 Map-Reduce")
    
    document = state.get("query", "")
    
    # 1. Split: 分片
    chunk_size = 500
    chunks = [document[i:i+chunk_size] for i in range(0, len(document), chunk_size)]
    
    if len(chunks) <= 1:
        # 文档太短，直接返回
        return {
            "chunks": [document],
            "chunk_summaries": [document],
            "final_summary": document,
            "messages": [AIMessage(content="文档较短，无需分片")]
        }
    
    logger.info(f"文档分为 {len(chunks)} 个分片")
    
    # 2. Map: 对每个分片生成摘要
    llm = get_llm()
    chunk_summaries = []
    
    for i, chunk in enumerate(chunks):
        summary_prompt = f"请用一句话总结以下内容：{chunk}"
        summary_response = llm.invoke([HumanMessage(content=summary_prompt)])
        chunk_summaries.append(summary_response.content)
        logger.info(f"分片 {i+1}/{len(chunks)} 摘要完成")
    
    # 3. Reduce: 合并所有摘要
    reduce_prompt = f"""请将以下多个摘要合并为一个完整的总结：

{chr(10).join([f"摘要{i+1}: {s}" for i, s in enumerate(chunk_summaries)])}

请提供一个连贯、完整的总结："""
    
    reduce_response = llm.invoke([HumanMessage(content=reduce_prompt)])
    
    logger.info("Map-Reduce 完成")
    
    return {
        "chunks": chunks,
        "chunk_summaries": chunk_summaries,
        "final_summary": reduce_response.content,
        "messages": [AIMessage(content="Map-Reduce 处理完成")]
    }


# ============================================================
# 节点5：并行执行
# ============================================================

def parallel_node(state: MasterState) -> dict:
    """
    并行执行节点
    
    将任务拆分为多个子任务并行处理。
    
    学习要点：
    - Fan-out: 分发任务到多个 Worker
    - Fan-in: 收集所有 Worker 结果
    - 适合独立子任务
    """
    logger.info("执行并行处理")
    
    query = state.get("query", "")
    
    # 模拟并行任务
    tasks = [
        {"id": 1, "task": f"任务1: 搜索 {query}"},
        {"id": 2, "task": f"任务2: 分析 {query}"},
        {"id": 3, "task": f"任务3: 总结 {query}"},
    ]
    
    # 模拟并行执行（实际应该用 asyncio.gather）
    worker_results = []
    for task in tasks:
        # 模拟 Worker 处理
        result = f"任务{task['id']}完成: 处理了 '{query}'"
        worker_results.append({"task_id": task["id"], "result": result})
    
    # 聚合结果
    aggregated = "并行处理结果：" + "; ".join([r["result"] for r in worker_results])
    
    logger.info("并行处理完成")
    
    return {
        "parallel_tasks": tasks,
        "worker_results": worker_results,
        "aggregated_result": aggregated,
        "messages": [AIMessage(content="并行处理完成")]
    }


# ============================================================
# 节点6：动态工具选择
# ============================================================

def dynamic_tools_node(state: MasterState) -> dict:
    """
    动态工具选择节点
    
    根据任务类型选择合适的工具子集。
    
    学习要点：
    - 不是所有任务都需要所有工具
    - 动态选择可以减少 Token 消耗
    - 提高工具调用准确性
    """
    logger.info("执行动态工具选择")
    
    task_analysis = state.get("task_analysis", {})
    task_type = task_analysis.get("task_type", "simple")
    
    # 根据任务类型选择工具
    if task_type == "search":
        selected = ["web_search", "search_knowledge"]
    elif task_type == "document":
        selected = ["calculate", "get_current_time"]
    else:
        selected = ["get_weather", "get_current_time"]
    
    logger.info(f"选择工具: {selected}")
    
    return {
        "selected_tools": selected,
        "messages": [AIMessage(content=f"选择工具: {', '.join(selected)}")]
    }


# ============================================================
# 节点7：Agent 推理
# ============================================================

def agent_node(state: MasterState) -> dict:
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

    # 调用 LLM
    logger.info(f"Agent 输入消息数: {len(messages)}")
    response = llm_with_tools.invoke(messages)
    
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
# 节点8：工具执行
# ============================================================

async def tool_node_master(state: MasterState) -> dict:
    """
    工具执行节点（Master 版本）

    .. deprecated::
        自 v2 防死循环重构起，已被 `PrebuiltToolNode` 替代。
        当前函数保留仅为向后兼容，新代码请使用 build_master_graph() 中
        的 `prebuilt_tools` 节点。后续版本将删除。

    执行 Agent 请求的工具调用，支持本地工具和 MCP 动态工具。

    学习要点：
    - 通过 tool_manager 统一查找工具（本地 + MCP）
    - MCP 工具（带 coroutine）走异步执行
    - 本地工具走同步执行
    - 错误重试机制
    - 结果存储到状态
    - 增加调用计数器防止死循环
    """
    from langchain_core.messages import ToolMessage
    
    logger.info("执行工具调用")
    
    messages = state.get("messages", [])
    last_message = messages[-1]
    
    # 获取当前调用次数
    tool_call_count = state.get("tool_call_count", 0)
    
    tool_results = {}
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        for tool_call in last_message.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
            logger.info(f"准备执行工具: {tool_name}, 参数: {tool_args}")
            
            # 通过 tool_manager 查找工具（本地 + MCP）
            tool = tool_manager.find_tool(tool_name)
            
            if tool:
                try:
                    # 判断工具类型：MCP 工具走异步，本地工具走同步
                    if hasattr(tool, 'coroutine') and tool.coroutine is not None:
                        logger.info(f"执行异步工具: {tool_name}")
                        result = await tool.ainvoke(tool_args)
                        logger.info(f"MCP 工具 {tool_name} 执行成功")
                    else:
                        logger.info(f"执行同步工具: {tool_name}")
                        result = tool.invoke(tool_args)
                        logger.info(f"本地工具 {tool_name} 执行成功")
                    
                    # 打印工具返回结果
                    result_str = str(result)
                    if len(result_str) > 500:
                        logger.info(f"工具 {tool_name} 返回结果(前500字符): {result_str[:500]}...")
                    else:
                        logger.info(f"工具 {tool_name} 返回结果: {result_str}")
                    
                    tool_results[tool_name] = result
                except Exception as e:
                    logger.error(f"工具 {tool_name} 执行失败: {e}")
                    tool_results[tool_name] = f"错误: {e}"
            else:
                logger.warning(f"工具 {tool_name} 未找到")
                tool_results[tool_name] = "工具未找到"
    
    # 构建工具消息
    tool_messages = [
        ToolMessage(content=str(result), tool_call_id=tc["id"])
        for tc in last_message.tool_calls
        for tool_call_id, result in [(tc["id"], tool_results.get(tc["name"], "未知"))]
        if tc["name"] in tool_results
    ]
    
    # 增加调用计数
    new_count = tool_call_count + 1
    logger.info(f"工具调用次数: {new_count}")
    
    return {
        "tool_results": tool_results,
        "messages": tool_messages,
        "tool_call_count": new_count,
    }


# ============================================================
# 节点9：人机协作
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
    last_message = messages[-1]
    
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
# 节点10：自我反思
# ============================================================

def reflection_node(state: MasterState) -> dict:
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
            "messages": [AIMessage(content="达到最大重试次数")]
        }
    
    # 获取最后一条 AI 消息
    ai_messages = [m for m in messages if isinstance(m, AIMessage)]
    if not ai_messages:
        return {
            "reflection": {"is_satisfactory": True, "confidence": 1.0},
            "messages": []
        }
    
    last_response = ai_messages[-1].content
    
    # 使用 LLM 进行反思
    llm = get_llm()
    
    try:
        structured_llm = llm.with_structured_output(ReflectionResult)
        
        reflection: ReflectionResult = structured_llm.invoke([
            SystemMessage(content="你是一个质量评估专家。评估 AI 的回答是否准确、完整、有用。"),
            HumanMessage(content=f"请评估以下回答：{last_response}")
        ])
        
        logger.info(f"反思结果: satisfactory={reflection.is_satisfactory}, confidence={reflection.confidence}")
        
        return {
            "reflection": reflection.model_dump(),
            "retry_count": retry_count + 1 if not reflection.is_satisfactory else retry_count,
            "messages": [AIMessage(content=f"反思完成: 满意度={reflection.is_satisfactory}")]
        }
    
    except Exception as e:
        logger.error(f"反思失败: {e}")
        return {
            "reflection": {"is_satisfactory": True, "confidence": 0.5},
            "messages": [AIMessage(content="反思失败，继续执行")]
        }


# ============================================================
# ============================================================
# 节点12：输出安全过滤
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
# 节点12：汇总节点
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
    
    if state.get("aggregated_result"):
        results.append(f"并行结果: {state['aggregated_result']}")
    
    if state.get("tool_results"):
        results.append(f"工具结果: {state['tool_results']}")
    
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
        from langchain_core.messages import ToolMessage
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
        "messages": [AIMessage(content=final_response)]
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
    
    # 1. 动态获取 MCP 工具列表
    mcp_tools = []
    try:
        if await mcp_client.health_check():
            mcp_tools = await mcp_client.list_tools()
            logger.info(f"获取到 {len(mcp_tools)} 个 MCP 工具")
        else:
            logger.warning("MCP Server 不可用")
    except Exception as e:
        logger.error(f"获取 MCP 工具失败: {e}")
    
    # 2. 动态获取 A2A Agent 列表
    a2a_agents = []
    try:
        if await a2a_client.health_check():
            a2a_agents = await a2a_client.list_agents()
            logger.info(f"获取到 {len(a2a_agents)} 个 A2A Agent")
        else:
            logger.warning("A2A Server 不可用")
    except Exception as e:
        logger.error(f"获取 A2A Agent 失败: {e}")
    
    # 3. 构建能力描述
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
    
    # 4. LLM 自主选择使用哪些能力
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
        HumanMessage(content=query)
    ])
    
    logger.info(f"能力选择结果: {selection}")
    
    # 5. 执行选定的能力
    results = []
    
    # 执行 MCP 工具
    for tool_name in selection.selected_mcp_tools:
        try:
            # 根据工具类型构造参数
            args = {}
            if "file" in tool_name:
                args = {"path": "example.txt"}
            elif "db" in tool_name:
                args = {"sql": "SELECT 1"}
            elif "http" in tool_name:
                args = {"url": "https://httpbin.org/get"}
            elif "code" in tool_name:
                args = {"code": "print('hello')"}
            
            result = await mcp_client.call_tool(tool_name, args)
            results.append({
                "type": "mcp",
                "tool": tool_name,
                "result": result
            })
            logger.info(f"MCP 工具 {tool_name} 执行完成")
        except Exception as e:
            logger.error(f"MCP 工具 {tool_name} 执行失败: {e}")
            results.append({
                "type": "mcp",
                "tool": tool_name,
                "error": str(e)
            })
    
    # 执行 A2A Agent
    for agent_name in selection.selected_a2a_agents:
        try:
            input_data = {
                "query": query,
                "context": "自动探索任务"
            }
            result = await a2a_client.create_task(agent_name, input_data)
            results.append({
                "type": "a2a",
                "agent": agent_name,
                "result": result
            })
            logger.info(f"A2A Agent {agent_name} 执行完成")
        except Exception as e:
            logger.error(f"A2A Agent {agent_name} 执行失败: {e}")
            results.append({
                "type": "a2a",
                "agent": agent_name,
                "error": str(e)
            })
    
    # 6. 汇总结果
    summary_parts = []
    for r in results:
        if r.get("error"):
            summary_parts.append(f"[{r['type']}] {r.get('tool') or r.get('agent')}: 错误 - {r['error']}")
        else:
            summary_parts.append(f"[{r['type']}] {r.get('tool') or r.get('agent')}: 成功")
    
    summary = "\n".join(summary_parts) if summary_parts else "未执行任何外部能力"
    
    logger.info("动态探索完成")
    
    return {
        "discovered_tools": mcp_tools,
        "discovered_agents": a2a_agents,
        "mcp_tool_calls": [{"tool": r.get("tool"), "args": {}} for r in results if r["type"] == "mcp"],
        "mcp_results": [r for r in results if r["type"] == "mcp"],
        "a2a_result": {"results": [r for r in results if r["type"] == "a2a"]},
        "messages": [AIMessage(content=f"动态探索完成:\n{summary}")]
    }


# ============================================================
# 路由函数
# ============================================================

def route_after_guard_input(state: MasterState) -> str:
    """输入安全检查后的路由"""
    if not state.get("input_safe", True):
        return "summarizer"  # 不安全，直接结束
    return "router"


def route_after_router(state: MasterState) -> str:
    """路由器后的路由"""
    return state.get("next_route", "agent")


def route_after_agent(state: MasterState) -> str:
    """
    Agent 推理后的路由（v2 —— 防死循环重构）

    新流程：所有"有 tool_calls"的情况都先经过 stuck_guard 节点。
    - 无 tool_calls：直接进入 reflection
    - 有 tool_calls：进入 stuck_guard（防抖守卫）

    实际 max_tool_calls 硬限转移到 route_after_human_review 中检查，
    避免在 agent 之后立即打断 LLM。
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
        - _force_skip_tools=True → 跳到 reflection（不再进入 tools）
        - 否则 → 进入 human_review
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
    # DEBUG: 打印路由决策的关键状态值
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


def route_after_tools(state: MasterState) -> str:
    """
    工具执行后的路由
    
    注：MCP 和 A2A 工具已动态注册为 LangChain Tool，Agent 可直接调用，
    无需经过此路由节点。工具执行后直接回到 Agent 生成最终回答。
    """
    return "agent"


def route_after_reflection(state: MasterState) -> str:
    """反思后的路由"""
    reflection = state.get("reflection", {})
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)
    
    if reflection.get("is_satisfactory", True) or retry_count >= max_retries:
        return "guard_output"  # 满意或达到最大重试，进入输出过滤
    else:
        return "agent"  # 不满意，重试


# ============================================================
# 构建统一大图
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


def build_master_graph():
    """
    构建统一大图（v2 —— 防死循环重构）

    流程图：
        START → guard_input → router → [research_subgraph/mapreduce/parallel/agent]
              → [research_subgraph/mapreduce/parallel] → agent
              → agent → stuck_guard → human_review → tools → agent (循环)
                                       └─(_force_skip/未批准/超限)→ reflection
              → reflection → guard_output → summarizer → END

    三层防死循环：
        1. stuck_guard：连续 N 次相同 (tool, args) 立即拦截
        2. max_tool_calls：累计硬上限（默认 5）
        3. recursion_limit：chat.py 调用处兜底（默认 15）

    学习要点：
        - 所有功能集成在一个图中
        - 通过条件路由实现分支
        - 防循环责任分层：业务层（stuck_guard）+ 资源层（max_tool_calls）+ 框架层（recursion_limit）
        - 带 checkpointer 支持时间旅行
    """
    logger.info("构建统一大图（v2 防死循环重构）")

    workflow = StateGraph(MasterState)

    # ============================================================
    # 添加所有节点
    # ============================================================
    workflow.add_node("guard_input", guard_input_node)
    workflow.add_node("router", router_node)
    workflow.add_node("research_subgraph", research_subgraph_node)
    workflow.add_node("mapreduce", mapreduce_node)
    workflow.add_node("parallel", parallel_node)
    workflow.add_node("dynamic_tools", dynamic_tools_node)
    workflow.add_node("agent", agent_node)

    # v2 新增：stuck_guard 守卫节点
    workflow.add_node("stuck_guard", _stuck_guard_node_wrapper)

    # v2 重构：使用 PrebuiltToolNode 替代手写 tool_node_master
    #         行为等价但更稳定（支持 handle_tool_errors、并发调用等）
    prebuilt_tools = _build_prebuilt_tool_node()
    workflow.add_node("tools", prebuilt_tools)

    workflow.add_node("human_review", human_review_node)
    workflow.add_node("reflection", reflection_node)
    workflow.add_node("guard_output", guard_output_node)
    workflow.add_node("summarizer", summarizer_node)

    # ============================================================
    # 边：入口与分叉
    # ============================================================
    workflow.set_entry_point("guard_input")

    workflow.add_conditional_edges(
        "guard_input",
        route_after_guard_input,
        {
            "router": "router",
            "summarizer": "summarizer"
        }
    )

    workflow.add_conditional_edges(
        "router",
        route_after_router,
        {
            "research_subgraph": "research_subgraph",
            "mapreduce": "mapreduce",
            "parallel": "parallel",
            "agent": "agent"
        }
    )

    # 所有处理路径最终汇聚到 agent
    workflow.add_edge("research_subgraph", "agent")
    workflow.add_edge("mapreduce", "agent")
    workflow.add_edge("parallel", "agent")

    # ============================================================
    # 边：核心循环（v2 —— 含 stuck_guard）
    # ============================================================

    # agent → stuck_guard（始终先经过防抖）或 reflection（无 tool_calls）
    workflow.add_conditional_edges(
        "agent",
        route_after_agent,
        {
            "stuck_guard": "stuck_guard",
            "reflection": "reflection"
        }
    )

    # stuck_guard → human_review（正常）或 reflection（强制跳过）
    workflow.add_conditional_edges(
        "stuck_guard",
        route_after_stuck_guard_wrapper,
        {
            "human_review": "human_review",
            "reflection": "reflection"
        }
    )

    # human_review → tools（批准 + 未超限）或 reflection（拒绝/超限）
    workflow.add_conditional_edges(
        "human_review",
        route_after_human_review,
        {
            "tools": "tools",
            "reflection": "reflection"
        }
    )

    # tools → agent（工具执行后回到 Agent 生成最终回答）
    workflow.add_edge("tools", "agent")

    # ============================================================
    # 边：尾部（反思 → 输出过滤 → 汇总）
    # ============================================================
    workflow.add_conditional_edges(
        "reflection",
        route_after_reflection,
        {
            "guard_output": "guard_output",
            "agent": "agent"
        }
    )

    workflow.add_edge("guard_output", "summarizer")
    workflow.add_edge("summarizer", END)

    # ============================================================
    # 编译（带 checkpointer 支持时间旅行）
    # ============================================================
    graph = workflow.compile(checkpointer=memory_manager.checkpointer)

    logger.info("统一大图构建完成（v2）")
    return graph


# 全局图实例
master_graph = build_master_graph()


# ============================================================
# 使用示例
# ============================================================
"""
使用示例：

# 1. 准备输入
initial_state = {
    "messages": [HumanMessage(content="北京今天天气怎么样？")],
    "query": "北京今天天气怎么样？",
    "conversation_id": "test-123",
    "input_safe": True,
    "output_safe": True,
    "guard_warnings": [],
    "task_analysis": None,
    "next_route": None,
    "research_result": None,
    "research_sources": [],
    "document": None,
    "chunks": [],
    "chunk_summaries": [],
    "final_summary": None,
    "parallel_tasks": [],
    "worker_results": [],
    "aggregated_result": None,
    "selected_tools": [],
    "tool_results": {},
    "mcp_tool_calls": [],
    "mcp_results": [],
    "a2a_task_id": None,
    "a2a_result": None,
    "pending_action": None,
    "human_feedback": None,
    "approved": False,
    "reflection": None,
    "retry_count": 0,
    "max_retries": 3,
    "tool_call_count": 0,
    "max_tool_calls": 5,
    "stuck_signature": None,
    "stuck_count": 0,
    "_force_skip_tools": False,
    "final_response": None,
}

# 2. 执行图
config = {"configurable": {"thread_id": "test-123"}}
result = master_graph.invoke(initial_state, config)

# 3. 获取结果
print("最终响应:", result["final_response"])
print("任务分析:", result["task_analysis"])
print("工具结果:", result["tool_results"])
"""
