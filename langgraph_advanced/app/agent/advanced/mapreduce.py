# -*- coding: utf-8 -*-
"""
Map-Reduce 模式实现

Map-Reduce 是大数据处理的经典模式，在 AI Agent 中常用于：
- 长文档摘要
- 批量数据处理
- 多文件分析

学习要点：
1. Map 阶段：将大任务拆分为多个小任务，并行处理
2. Reduce 阶段：将所有小任务的结果汇总，生成最终结果
3. 与并行执行的区别：Map-Reduce 强调"分片→处理→汇总"
4. 使用 Send API 实现 Map 阶段的动态分片

架构图：
    splitter → [mapper1, mapper2, mapper3] → reducer → END
        ↓            ↓           ↓           ↓
    拆分文档      处理分片1    处理分片2    处理分片3
        ↓            ↓           ↓           ↓
        └────────────┴───────────┴───────────┘
                        ↓
                  汇总所有分片结果
"""

from typing import Annotated, List, Optional
from typing_extensions import TypedDict

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.constants import Send

from app.agent.nodes import get_llm
from app.core.logging import get_logger

logger = get_logger(__name__)


# ============================================================
# Map-Reduce 状态定义
# ============================================================
class MapReduceState(TypedDict):
    """
    Map-Reduce 状态
    
    包含 Map-Reduce 各阶段所需的数据：
    - messages: 对话消息
    - document: 原始文档（输入）
    - chunks: 分片后的数据块（Map 阶段输入）
    - chunk_summaries: 每个分片的摘要（Map 阶段输出）
    - final_summary: 最终汇总结果（Reduce 阶段输出）
    """
    # 消息列表
    messages: Annotated[List[BaseMessage], add_messages]
    
    # 原始文档
    document: str
    
    # 分片后的数据块
    chunks: List[str]
    
    # 每个分片的摘要
    chunk_summaries: List[str]
    
    # 最终汇总结果
    final_summary: Optional[str]


# ============================================================
# 节点1: 分片节点（Splitter）
# ============================================================
def splitter_node(state: MapReduceState) -> dict:
    """
    分片节点 - 将长文档拆分为多个小块
    
    分片策略：
    - 按字符数拆分（简单但可能切断句子）
    - 按段落拆分（保留语义完整性）
    - 按句子拆分（最细粒度）
    
    本示例使用按段落拆分。
    
    Args:
        state: Map-Reduce 状态
    
    Returns:
        dict: 状态更新（包含分片列表）
    
    学习要点：
    - 分片策略直接影响处理质量
    - 每个分片不能太大（超过 LLM 上下文限制）
    - 每个分片不能太小（丢失上下文）
    - 通常 500-2000 字符是一个好的分片大小
    """
    logger.info("执行分片节点")
    
    document = state.get("document", "")
    
    if not document:
        # 如果没有文档，从消息中提取
        messages = state.get("messages", [])
        document = messages[-1].content if messages else ""
    
    # 按段落拆分（以双换行符为分隔）
    paragraphs = document.split("\n\n")
    
    # 合并短段落，确保每个分片有足够内容
    chunks = []
    current_chunk = ""
    CHUNK_SIZE = 1000  # 目标分片大小（字符数）
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        # 如果当前分片加上新段落不超过目标大小，合并
        if len(current_chunk) + len(para) < CHUNK_SIZE:
            current_chunk += "\n\n" + para if current_chunk else para
        else:
            # 当前分片已满，保存并开始新分片
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = para
    
    # 保存最后一个分片
    if current_chunk:
        chunks.append(current_chunk)
    
    # 如果文档太短没有分片，整体作为一个分片
    if not chunks:
        chunks = [document]
    
    logger.info(f"文档拆分为 {len(chunks)} 个分片")
    for i, chunk in enumerate(chunks):
        logger.info(f"  分片 {i+1}: {len(chunk)} 字符")
    
    return {
        "document": document,
        "chunks": chunks,
        "chunk_summaries": [],
    }


# ============================================================
# 节点2: Mapper 节点（Map 阶段）
# ============================================================
def mapper_node(state: dict) -> dict:
    """
    Mapper 节点 - 处理单个分片
    
    这个节点会被并行调用多次，每次处理一个分片。
    使用 LLM 对每个分片生成摘要。
    
    Args:
        state: 单个分片的状态（包含 chunk 字段）
    
    Returns:
        dict: 分片摘要
    
    学习要点：
    - Mapper 节点是 Map 阶段的核心
    - 每个 Mapper 独立处理一个分片
    - 多个 Mapper 可以并行执行
    - 使用 LLM 进行智能摘要
    """
    chunk = state.get("chunk", "")
    chunk_index = state.get("chunk_index", 0)
    
    logger.info(f"Mapper 处理分片 {chunk_index + 1}（{len(chunk)} 字符）")
    
    # 使用 LLM 生成摘要
    llm = get_llm()
    
    summary_prompt = [
        SystemMessage(content=(
            "你是一个文档摘要专家。请对提供的内容生成简洁的摘要。\n"
            "要求：\n"
            "1. 提取关键信息\n"
            "2. 保留重要细节\n"
            "3. 摘要控制在 200 字以内\n"
            "4. 使用清晰的表述"
        )),
        AIMessage(content=f"请摘要以下内容：\n\n{chunk}"),
    ]
    
    response = llm.invoke(summary_prompt)
    summary = response.content
    
    logger.info(f"Mapper 完成分片 {chunk_index + 1} 的摘要")
    
    return {
        "summary": summary,
    }


# ============================================================
# 节点3: Reducer 节点（Reduce 阶段）
# ============================================================
def reducer_node(state: MapReduceState) -> dict:
    """
    Reducer 节点 - 汇总所有分片摘要
    
    这个节点负责：
    1. 收集所有 Mapper 生成的摘要
    2. 使用 LLM 整合摘要
    3. 生成最终的汇总结果
    
    Args:
        state: Map-Reduce 状态
    
    Returns:
        dict: 状态更新（包含最终汇总）
    
    学习要点：
    - Reducer 是 Reduce 阶段的核心
    - 等待所有 Mapper 完成后执行
    - 使用 LLM 进行智能汇总
    - 最终结果应该比单个摘要更全面
    """
    logger.info("执行 Reducer 节点")
    
    chunk_summaries = state.get("chunk_summaries", [])
    
    if not chunk_summaries:
        logger.warning("没有分片摘要可汇总")
        return {
            "final_summary": "未获取到任何分片摘要",
            "messages": [AIMessage(content="未获取到任何分片摘要")],
        }
    
    logger.info(f"汇总 {len(chunk_summaries)} 个分片摘要")
    
    # 使用 LLM 汇总所有摘要
    llm = get_llm()
    
    reduce_prompt = [
        SystemMessage(content=(
            "你是一个文档汇总专家。根据提供的多个分片摘要，生成一份完整的汇总报告。\n"
            "要求：\n"
            "1. 整合所有分片的关键信息\n"
            "2. 保持逻辑连贯性\n"
            "3. 去除重复内容\n"
            "4. 生成结构清晰的最终报告"
        )),
        AIMessage(content=(
            f"以下是 {len(chunk_summaries)} 个分片的摘要：\n\n" +
            "\n\n---\n\n".join([
                f"【分片 {i+1} 摘要】\n{s}"
                for i, s in enumerate(chunk_summaries)
            ])
        )),
    ]
    
    response = llm.invoke(reduce_prompt)
    final_summary = response.content
    
    logger.info("Reducer 完成汇总")
    
    return {
        "final_summary": final_summary,
        "messages": [AIMessage(content=final_summary)],
    }


# ============================================================
# 路由函数：动态创建 Map 任务
# ============================================================
def route_to_mappers(state: MapReduceState) -> list:
    """
    路由到 Mapper 节点 - 为每个分片创建并行任务
    
    Args:
        state: Map-Reduce 状态
    
    Returns:
        list: Send 对象列表
    
    学习要点：
    - 使用 Send API 为每个分片创建并行任务
    - 每个 Send 包含分片内容和索引
    - LangGraph 自动并行执行所有 Mapper
    """
    chunks = state.get("chunks", [])
    
    if not chunks:
        logger.warning("没有分片可处理")
        return []
    
    # 为每个分片创建一个 Send 对象
    sends = [
        Send("mapper", {"chunk": chunk, "chunk_index": i})
        for i, chunk in enumerate(chunks)
    ]
    
    logger.info(f"创建 {len(sends)} 个并行 Mapper 任务")
    return sends


# ============================================================
# 收集 Mapper 结果
# ============================================================
def collect_mapper_results(state: MapReduceState) -> dict:
    """
    收集 Mapper 结果节点
    
    在所有 Mapper 完成后，收集它们的输出。
    
    学习要点：
    - 这个节点在 Mapper 和 Reducer 之间
    - 负责将分散的 Mapper 结果汇总到状态中
    - 为 Reducer 准备输入数据
    """
    logger.info("收集 Mapper 结果")
    
    # 注意：在实际的 LangGraph 中，Mapper 的结果会通过状态自动传递
    # 这里简化处理，从状态中获取
    chunk_summaries = state.get("chunk_summaries", [])
    
    return {
        "chunk_summaries": chunk_summaries,
    }


# ============================================================
# 构建 Map-Reduce 图
# ============================================================
def build_mapreduce_graph():
    """
    构建 Map-Reduce 图
    
    流程：
        START → splitter → [mapper1, mapper2, ...] → reducer → END
    
    学习要点：
    - 这是经典的 Map-Reduce 模式
    - Splitter 负责分片
    - Mapper 并行处理每个分片
    - Reducer 汇总所有结果
    - 适用于长文档处理、批量数据分析
    
    Returns:
        CompiledGraph: 编译后的 Map-Reduce 图
    """
    logger.info("构建 Map-Reduce 图")
    
    # 创建状态图
    workflow = StateGraph(MapReduceState)
    
    # 添加节点
    workflow.add_node("splitter", splitter_node)
    workflow.add_node("mapper", mapper_node)
    workflow.add_node("reducer", reducer_node)
    
    # 设置入口点
    workflow.set_entry_point("splitter")
    
    # splitter → mappers（动态创建并行任务）
    workflow.add_conditional_edges(
        "splitter",
        route_to_mappers,
        ["mapper"]
    )
    
    # mappers → reducer
    workflow.add_edge("mapper", "reducer")
    
    # reducer → END
    workflow.add_edge("reducer", END)
    
    # 编译图
    graph = workflow.compile()
    
    logger.info("Map-Reduce 图构建完成")
    return graph


# 全局图实例
mapreduce_graph = build_mapreduce_graph()


# ============================================================
# 使用示例
# ============================================================
"""
使用示例：

# 1. 准备长文档
long_document = '''
第一章：引言
这是文档的第一章内容...

第二章：方法
这是文档的第二章内容...

第三章：结果
这是文档的第三章内容...

第四章：结论
这是文档的第四章内容...
'''

# 2. 准备初始状态
initial_state = {
    "messages": [HumanMessage(content="请总结这篇文档")],
    "document": long_document,
    "chunks": [],
    "chunk_summaries": [],
    "final_summary": None,
}

# 3. 执行 Map-Reduce 图
result = mapreduce_graph.invoke(initial_state)

# 4. 获取最终汇总
print(result["final_summary"])
"""
