# -*- coding: utf-8 -*-
"""
Map-Reduce 工具函数（共享组件）

提供文本分片、并行摘要等可复用函数。
master_graph 和 subagent_graph 都依赖这些函数。
"""

from typing import List

from langchain_core.messages import HumanMessage

from app.agent.shared.llm import get_llm
from app.core.logging import get_logger

logger = get_logger(__name__)


# 每个分片最大字符数（控制在 LLM 上下文窗口内）
MAX_CHUNK_CHARS = 800


def split_text(text: str, max_size: int = MAX_CHUNK_CHARS) -> List[str]:
    """
    智能分片：优先按段落分割，段落超长时按句号 fallback，再不行按字符硬切。

    Args:
        text: 待分片的文本
        max_size: 每个分片的最大字符数

    Returns:
        分片列表
    """
    # 第一层：按空行分割段落
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) <= 1:
        # 没有段落分隔，按单换行分割
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    # 第二层：合并短段落 / 拆分超长段落
    chunks: List[str] = []
    buffer = ""
    for para in paragraphs:
        if len(para) > max_size:
            # 段落超长：先 flush buffer，再按句号拆分
            if buffer:
                chunks.append(buffer)
                buffer = ""
            sentences = para.replace("。", "。\n").replace(".", ".\n").split("\n")
            for sent in sentences:
                sent = sent.strip()
                if not sent:
                    continue
                if len(sent) > max_size:
                    # 句子也超长：硬切
                    for i in range(0, len(sent), max_size):
                        chunks.append(sent[i:i + max_size])
                elif len(buffer) + len(sent) <= max_size:
                    buffer += sent
                else:
                    if buffer:
                        chunks.append(buffer)
                    buffer = sent
        elif len(buffer) + len(para) + 2 <= max_size:
            # 段落可以追加到 buffer
            buffer = f"{buffer}\n\n{para}" if buffer else para
        else:
            # buffer 满了，flush
            if buffer:
                chunks.append(buffer)
            buffer = para

    if buffer:
        chunks.append(buffer)

    return chunks


async def map_summarize_chunk(idx: int, chunk: str, total: int) -> str:
    """
    对单个分片生成结构化摘要（异步，供 mapreduce_node 和压缩中间件复用）

    Args:
        idx: 分片索引（用于日志）
        chunk: 分片内容
        total: 总分片数（用于日志）

    Returns:
        分片的摘要文本
    """
    llm = get_llm()
    map_prompt = (
        f"请提取以下内容的关键信息，按要点列出：\n"
        f"1. 主要观点（核心论点）\n"
        f"2. 重要数据（数字、百分比、日期等）\n"
        f"3. 关键结论（作者的建议或判断）\n\n"
        f"内容：\n{chunk}"
    )
    response = await llm.ainvoke([HumanMessage(content=map_prompt)])
    logger.info(f"分片 {idx + 1}/{total} 摘要完成")
    return response.content
