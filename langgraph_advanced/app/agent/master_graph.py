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

from typing import List, Optional, Dict, Any, Annotated
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from app.agent.nodes import get_llm, TOOLS, tool_node
from app.memory import memory_manager
from app.core.config import settings
from app.core.logging import get_logger
from app.agent.mcp.simple_client import mcp_client
from app.agent.a2a.simple_client import a2a_client

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
    
    # 人机协作
    pending_action: Optional[str]       # 待确认操作
    human_feedback: Optional[str]       # 人工反馈
    approved: bool                      # 是否批准
    
    # 自我反思
    reflection: Optional[dict]          # 反思结果
    retry_count: int                    # 重试次数
    max_retries: int                    # 最大重试次数
    
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
# 节点2：路由器（意图分类 + 结构化输出）
# ============================================================

def router_node(state: MasterState) -> dict:
    """
    路由器节点
    
    分析用户意图，决定任务类型和处理路径。
    使用结构化输出确保返回格式正确。
    
    学习要点：
    - 使用 with_structured_output 强制返回 JSON
    - 根据任务类型决定后续路由
    - 简单问题直接回答，复杂问题分发到子图
    """
    logger.info("执行路由器（意图分类）")
    
    query = state.get("query", "")
    
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
        
        return {
            "task_analysis": task_analysis.model_dump(),
            "next_route": next_route,
            "messages": [AIMessage(content=f"任务分类: {task_analysis.task_type}")]
        }
    
    except Exception as e:
        logger.error(f"路由失败: {e}")
        # 默认走简单路径
        return {
            "task_analysis": {
                "task_type": "simple",
                "priority": "medium",
                "complexity": 5,
                "description": query,
                "requires_tools": False
            },
            "next_route": "agent",
            "messages": [AIMessage(content="任务分类失败，使用默认路径")]
        }


# ============================================================
# 节点3：研究子图
# ============================================================

def research_subgraph_node(state: MasterState) -> dict:
    """
    研究子图节点
    
    执行搜索-分析-编译流程。
    
    学习要点：
    - 子图作为大图中的一个节点
    - 子图内部可以有多个节点
    - 子图结果返回给大图继续处理
    """
    logger.info("执行研究子图")
    
    query = state.get("query", "")
    
    # 这里简化实现，实际应该调用 research_graph
    # 模拟研究过程
    llm = get_llm()
    
    # 1. 搜索（模拟）
    search_results = [
        f"搜索结果1: 关于 '{query}' 的信息...",
        f"搜索结果2: 相关数据...",
        f"搜索结果3: 最新进展..."
    ]
    
    # 2. 分析
    analysis_prompt = f"""基于以下搜索结果，分析并总结关键信息：

搜索结果：
{chr(10).join(search_results)}

用户问题：{query}

请提供简洁的分析总结："""
    
    analysis_response = llm.invoke([HumanMessage(content=analysis_prompt)])
    
    # 3. 编译报告
    report = f"""
研究报告：{query}

关键发现：
{chr(10).join([f"- {r}" for r in search_results])}

分析总结：
{analysis_response.content}
"""
    
    logger.info("研究子图完成")
    
    return {
        "research_result": report,
        "research_sources": search_results,
        "messages": [AIMessage(content="研究完成")]
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
    
    # 获取 LLM
    llm = get_llm()
    llm_with_tools = llm.bind_tools(TOOLS)
    
    # 调用 LLM
    response = llm_with_tools.invoke(messages)
    
    logger.info(f"Agent 推理完成，工具调用: {len(response.tool_calls)}")
    
    return {
        "messages": [response],
    }


# ============================================================
# 节点8：工具执行
# ============================================================

def tool_node_master(state: MasterState) -> dict:
    """
    工具执行节点（Master 版本）
    
    执行 Agent 请求的工具调用。
    
    学习要点：
    - 支持内部工具和 MCP 工具
    - 错误重试机制
    - 结果存储到状态
    """
    logger.info("执行工具调用")
    
    messages = state.get("messages", [])
    last_message = messages[-1]
    
    tool_results = {}
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        for tool_call in last_message.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
            # 查找工具
            tool = None
            for t in TOOLS:
                if t.name == tool_name:
                    tool = t
                    break
            
            if tool:
                try:
                    result = tool.invoke(tool_args)
                    tool_results[tool_name] = result
                    logger.info(f"工具 {tool_name} 执行成功")
                except Exception as e:
                    logger.error(f"工具 {tool_name} 执行失败: {e}")
                    tool_results[tool_name] = f"错误: {e}"
            else:
                logger.warning(f"工具 {tool_name} 未找到")
                tool_results[tool_name] = "工具未找到"
    
    # 构建工具消息
    from langchain_core.messages import ToolMessage
    tool_messages = [
        ToolMessage(content=str(result), tool_call_id=tc["id"])
        for tc in last_message.tool_calls
        for tool_call_id, result in [(tc["id"], tool_results.get(tc["name"], "未知"))]
        if tc["name"] in tool_results
    ]
    
    return {
        "tool_results": tool_results,
        "messages": tool_messages,
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
        
        return {
            "pending_action": pending_action,
            "approved": approved,
            "human_feedback": human_feedback,
            "messages": [AIMessage(content=f"人工审核: {human_feedback}")]
        }
    
    return {
        "approved": True,
        "messages": [AIMessage(content="无需审核")]
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
# 节点11：MCP 工具调用
# ============================================================

async def mcp_tools_node(state: MasterState) -> dict:
    """
    MCP 工具调用节点
    
    调用外部 MCP Server 提供的工具。
    
    学习要点：
    - 通过 HTTP 连接独立的 mcp_server
    - 支持文件操作、数据库查询、HTTP 请求等
    - 结果存储到状态中
    """
    logger.info("执行 MCP 工具调用")
    
    query = state.get("query", "")
    mcp_results = []
    
    # 根据任务类型选择合适的 MCP 工具
    task_analysis = state.get("task_analysis", {})
    task_type = task_analysis.get("task_type", "simple")
    
    try:
        # 检查 MCP Server 是否可用
        if not await mcp_client.health_check():
            logger.warning("MCP Server 不可用")
            return {
                "mcp_tool_calls": [],
                "mcp_results": [{"error": "MCP Server 不可用"}],
                "messages": [AIMessage(content="MCP 服务不可用")]
            }
        
        # 示例：根据任务类型调用不同的工具
        if task_type == "document":
            # 文件操作：保存文档
            result = await mcp_client.call_tool("file_write", {
                "path": "document.txt",
                "content": query
            })
            mcp_results.append(result)
        
        elif task_type == "search":
            # HTTP 请求：搜索信息
            result = await mcp_client.call_tool("http_get", {
                "url": f"https://api.example.com/search?q={query}"
            })
            mcp_results.append(result)
        
        logger.info(f"MCP 工具调用完成，结果数: {len(mcp_results)}")
        
        return {
            "mcp_tool_calls": [{"tool": "mcp_tools", "task_type": task_type}],
            "mcp_results": mcp_results,
            "messages": [AIMessage(content="MCP 工具调用完成")]
        }
    
    except Exception as e:
        logger.error(f"MCP 工具调用失败: {e}")
        return {
            "mcp_tool_calls": [],
            "mcp_results": [{"error": str(e)}],
            "messages": [AIMessage(content=f"MCP 调用失败: {e}")]
        }


# ============================================================
# 节点12：A2A 协作
# ============================================================

async def a2a_collaboration_node(state: MasterState) -> dict:
    """
    A2A 协作节点
    
    调用外部 A2A Server 的专业 Agent 进行协作。
    
    学习要点：
    - 通过 HTTP 连接独立的 a2a_server
    - 支持研究、编码、翻译、分析等专业 Agent
    - 任务异步执行，获取结果
    """
    logger.info("执行 A2A 协作")
    
    query = state.get("query", "")
    task_analysis = state.get("task_analysis", {})
    task_type = task_analysis.get("task_type", "simple")
    
    try:
        # 检查 A2A Server 是否可用
        if not await a2a_client.health_check():
            logger.warning("A2A Server 不可用")
            return {
                "a2a_task_id": None,
                "a2a_result": None,
                "messages": [AIMessage(content="A2A 服务不可用")]
            }
        
        # 根据任务类型选择合适的 Agent
        agent_map = {
            "search": "researcher",
            "document": "analyzer",
            "parallel": "coder",
            "simple": "translator"
        }
        
        agent_name = agent_map.get(task_type, "researcher")
        
        # 创建任务
        task_result = await a2a_client.create_task(
            agent_name=agent_name,
            input_data={
                "query": query,
                "context": state.get("query", "")
            }
        )
        
        task_id = task_result.get("task_id")
        
        if task_result.get("status") == "completed":
            result = task_result.get("result", {})
            logger.info(f"A2A 协作完成，Agent: {agent_name}")
            
            return {
                "a2a_task_id": task_id,
                "a2a_result": result,
                "messages": [AIMessage(content=f"A2A 协作完成: {agent_name}")]
            }
        else:
            logger.warning(f"A2A 任务未完成: {task_result.get('status')}")
            return {
                "a2a_task_id": task_id,
                "a2a_result": None,
                "messages": [AIMessage(content="A2A 任务处理中")]
            }
    
    except Exception as e:
        logger.error(f"A2A 协作失败: {e}")
        return {
            "a2a_task_id": None,
            "a2a_result": None,
            "messages": [AIMessage(content=f"A2A 协作失败: {e}")]
        }


# ============================================================
# 节点13：输出安全过滤
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
    """Agent 推理后的路由"""
    messages = state.get("messages", [])
    last_message = messages[-1]
    
    # 检查是否有工具调用
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "human_review"  # 需要工具调用，先人工审核
    else:
        return "reflection"  # 没有工具调用，直接反思


def route_after_human_review(state: MasterState) -> str:
    """人工审核后的路由"""
    if state.get("approved", False):
        return "tools"  # 批准，执行工具
    else:
        return "reflection"  # 拒绝，直接反思


def route_after_tools(state: MasterState) -> str:
    """工具执行后的路由 - 根据任务类型决定是否调用 MCP/A2A"""
    task_type = state.get("task_analysis", {}).get("task_type", "simple")
    
    # 搜索类任务调用 MCP
    if task_type == "search":
        return "mcp_tools"
    
    # 文档类任务调用 A2A
    elif task_type == "document":
        return "a2a_collaboration"
    
    # 其他任务直接回到 Agent
    else:
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

def build_master_graph():
    """
    构建统一大图
    
    流程图：
        START → guard_input → router → [subgraph/mapreduce/parallel/agent]
              → agent → human_review → tools → agent (循环)
              → reflection → guard_output → summarizer → END
    
    学习要点：
    - 所有功能集成在一个图中
    - 通过条件路由实现分支
    - 支持循环（agent ↔ tools）
    - 带 checkpointer 支持时间旅行
    """
    logger.info("构建统一大图")
    
    workflow = StateGraph(MasterState)
    
    # 添加所有节点
    workflow.add_node("guard_input", guard_input_node)
    workflow.add_node("router", router_node)
    workflow.add_node("research_subgraph", research_subgraph_node)
    workflow.add_node("mapreduce", mapreduce_node)
    workflow.add_node("parallel", parallel_node)
    workflow.add_node("dynamic_tools", dynamic_tools_node)
    workflow.add_node("mcp_tools", mcp_tools_node)
    workflow.add_node("a2a_collaboration", a2a_collaboration_node)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node_master)
    workflow.add_node("human_review", human_review_node)
    workflow.add_node("reflection", reflection_node)
    workflow.add_node("guard_output", guard_output_node)
    workflow.add_node("summarizer", summarizer_node)
    
    # 设置入口点
    workflow.set_entry_point("guard_input")
    
    # 添加边
    # guard_input → router 或 summarizer（如果不安全）
    workflow.add_conditional_edges(
        "guard_input",
        route_after_guard_input,
        {
            "router": "router",
            "summarizer": "summarizer"
        }
    )
    
    # router → 根据任务类型分发
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
    
    # agent → human_review 或 reflection
    workflow.add_conditional_edges(
        "agent",
        route_after_agent,
        {
            "human_review": "human_review",
            "reflection": "reflection"
        }
    )
    
    # human_review → tools 或 reflection
    workflow.add_conditional_edges(
        "human_review",
        route_after_human_review,
        {
            "tools": "tools",
            "reflection": "reflection"
        }
    )
    
    # tools → mcp_tools/a2a_collaboration/agent（根据任务类型）
    workflow.add_conditional_edges(
        "tools",
        route_after_tools,
        {
            "mcp_tools": "mcp_tools",
            "a2a_collaboration": "a2a_collaboration",
            "agent": "agent"
        }
    )
    
    # mcp_tools → agent
    workflow.add_edge("mcp_tools", "agent")
    
    # a2a_collaboration → agent
    workflow.add_edge("a2a_collaboration", "agent")
    
    # reflection → guard_output 或 agent（重试）
    workflow.add_conditional_edges(
        "reflection",
        route_after_reflection,
        {
            "guard_output": "guard_output",
            "agent": "agent"
        }
    )
    
    # guard_output → summarizer
    workflow.add_edge("guard_output", "summarizer")
    
    # summarizer → END
    workflow.add_edge("summarizer", END)
    
    # 编译图（带 checkpointer 支持时间旅行）
    graph = workflow.compile(checkpointer=memory_manager.checkpointer)
    
    logger.info("统一大图构建完成")
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
    "pending_action": None,
    "human_feedback": None,
    "approved": False,
    "reflection": None,
    "retry_count": 0,
    "max_retries": 3,
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
