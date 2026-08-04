# -*- coding: utf-8 -*-
"""
基础对话路由

提供基础的 Agent 对话接口。
支持单 Agent、多 Agent、统一大图三种模式。
支持流式（SSE）和阻塞两种响应方式。

接口参数：
- mode: single / multi / master
- stream: true(流式) / false(阻塞，默认)
"""

import json
import uuid
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage

from app.agent.graph import agent_graph
from app.agent.multi_graph import multi_agent_graph
from app.agent.master_graph import master_graph
from app.schemas.chat import ChatRequest, ChatResponse, StepInfo
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ============================================================
# 步骤提取函数
# ============================================================

def extract_single_steps(result: dict) -> list:
    """
    从 single 模式结果中提取推理步骤
    
    Args:
        result: LangGraph 执行结果
    
    Returns:
        步骤列表
    """
    from langchain_core.messages import AIMessage, ToolMessage
    
    steps = []
    messages = result.get("messages", [])
    
    for msg in messages:
        if isinstance(msg, AIMessage):
            # Agent 推理步骤
            if msg.content:
                steps.append(StepInfo(
                    type="agent_reasoning",
                    content=msg.content
                ))
            
            # 工具调用步骤
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    steps.append(StepInfo(
                        type="tool_call",
                        content=f"调用工具: {tc['name']}",
                        tool_name=tc["name"],
                        tool_args=tc["args"]
                    ))
        
        elif isinstance(msg, ToolMessage):
            # 工具结果步骤
            steps.append(StepInfo(
                type="tool_result",
                content=f"工具 {msg.name} 返回结果",
                tool_name=msg.name,
                tool_result=msg.content
            ))
    
    return steps


def extract_multi_steps(result: dict) -> list:
    """
    从 multi 模式结果中提取推理步骤
    
    Args:
        result: LangGraph 执行结果
    
    Returns:
        步骤列表
    """
    from langchain_core.messages import AIMessage, ToolMessage
    
    steps = []
    messages = result.get("messages", [])
    
    for msg in messages:
        if isinstance(msg, AIMessage):
            if msg.content:
                steps.append(StepInfo(
                    type="agent_reasoning",
                    content=msg.content
                ))
            
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    steps.append(StepInfo(
                        type="tool_call",
                        content=f"调用工具: {tc['name']}",
                        tool_name=tc["name"],
                        tool_args=tc["args"]
                    ))
        
        elif isinstance(msg, ToolMessage):
            steps.append(StepInfo(
                type="tool_result",
                content=f"工具 {msg.name} 返回结果",
                tool_name=msg.name,
                tool_result=msg.content
            ))
    
    return steps


def extract_master_steps(result: dict) -> list:
    """
    从 master 模式结果中提取推理步骤
    
    Args:
        result: LangGraph 执行结果
    
    Returns:
        步骤列表
    """
    from langchain_core.messages import AIMessage, ToolMessage
    
    steps = []
    messages = result.get("messages", [])
    
    for msg in messages:
        if isinstance(msg, AIMessage):
            if msg.content:
                steps.append(StepInfo(
                    type="agent_reasoning",
                    content=msg.content
                ))
            
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    steps.append(StepInfo(
                        type="tool_call",
                        content=f"调用工具: {tc['name']}",
                        tool_name=tc["name"],
                        tool_args=tc["args"]
                    ))
        
        elif isinstance(msg, ToolMessage):
            steps.append(StepInfo(
                type="tool_result",
                content=f"工具 {msg.name} 返回结果",
                tool_name=msg.name,
                tool_result=msg.content
            ))
    
    # 添加最终响应步骤
    final_response = result.get("final_response")
    if final_response:
        steps.append(StepInfo(
            type="final_answer",
            content=final_response
        ))
    
    return steps


# ============================================================
# 流式响应生成器
# ============================================================

async def generate_stream_response(graph, initial_state: dict, config: dict, mode: str):
    """
    流式响应生成器（AG-UI 协议版）

    输出符合 AG-UI 标准的 SSE 事件流，所有事件统一格式：
        {"type": "<EventName>", "data": {...}}

    事件清单：
    - RunStarted          流开始
    - TextMessageStart    LLM 文本段开始（带 message id）
    - TextMessageContent  LLM 文本增量（content 字段）
    - TextMessageEnd      LLM 文本段结束
    - ToolCallStart       工具调用开始（name + args）
    - ToolCallEnd         工具调用结束（name + result）
    - StepStarted         主图节点开始（name）
    - StepFinished        主图节点结束（name）
    - StateDelta          状态变化（可选，当前未触发）
    - ReasoningSteps      推理步骤聚合（流末尾）
    - RunFinished         流正常结束
    - RunError            流异常结束（message）

    Args:
        graph: LangGraph 图实例
        initial_state: 初始状态
        config: 配置（含 thread_id + recursion_limit）
        mode: 运行模式 single/multi/master

    Yields:
        SSE 格式事件（每行 "data: {...}\\n\\n"）
    """
    # ----- 内部辅助：构造标准 AG-UI 事件 -----
    def sse(event_type: str, data: dict | None = None) -> str:
        """构造标准 AG-UI 事件载荷（type + 可选 data 嵌套对象）"""
        payload: dict = {"type": event_type}
        if data is not None:
            payload["data"] = data
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    # ----- 跨事件维持的状态 -----
    in_text: bool = False                  # 是否处于 TextMessage 流中
    text_msg_id: str = ""                  # 当前 TextMessage 的 id
    current_step: str = ""                 # 当前正在执行的图节点名
    reasoning_steps: list = []             # 推理步骤聚合（流末尾一次性发出）

    # 主图的节点白名单（用于过滤 astream_events 内部子 chain）
    # 单 Agent / 多 Agent 模式没有完整子图，放行所有 chain 事件
    master_node_whitelist: set[str] = {
        "guard_input", "router", "research_subgraph", "mapreduce", "parallel",
        "dynamic_tools", "agent", "stuck_guard", "tools", "human_review",
        "reflection", "guard_output", "summarizer",
    }

    try:
        # ==========================================================
        # 1) 流开始
        # ==========================================================
        yield sse("RunStarted", {
            "mode": mode,
            "conversation_id": (config.get("configurable") or {}).get("thread_id"),
        })

        # 2) 流式消费 LangGraph 事件
        # ==========================================================
        seen_kinds: set[str] = set()
        async for event in graph.astream_events(initial_state, config, version="v2"):
            kind: str = event.get("event", "")
            name: str = event.get("name", "unknown")
            data: dict = event.get("data", {}) or {}

            # 调试：把所有出现过的 kind 记录到日志（仅一次）
            if kind not in seen_kinds:
                seen_kinds.add(kind)
                logger.info(f"[AGUI-DEBUG] new kind={kind!r} name={name!r}")

            # ---- 2.1 主图节点开始 ----
            if kind == "on_chain_start":
                # 过滤：主图模式下仅对白名单节点广播 StepStarted
                if mode == "master" and name not in master_node_whitelist:
                    continue
                current_step = name
                yield sse("StepStarted", {"name": name})
                reasoning_steps.append({"type": "step", "name": name, "status": "started"})

            # ---- 2.2 主图节点结束 ----
            elif kind == "on_chain_end":
                if mode == "master" and name not in master_node_whitelist:
                    continue
                if name == current_step:
                    current_step = ""
                yield sse("StepFinished", {"name": name})
                # 更新聚合步骤状态（覆盖前一个 started）
                if reasoning_steps and reasoning_steps[-1].get("name") == name \
                        and reasoning_steps[-1].get("status") == "started":
                    reasoning_steps[-1]["status"] = "finished"

            # ---- 2.3 LLM 流式输出 ----
            elif kind == "on_chat_model_stream":
                # v3-fix：过滤内部节点的 LLM 流（router / dynamic_tools / reflection 等
                #         用了 with_structured_output，会输出 JSON 文本，
                #         不应该作为最终 AI 回复透传给前端）。
                # 仅放行最终面向用户的节点：agent。
                # 其他节点（reflection、summarizer）的输出是结构化评估/摘要数据，不透传。
                if mode == "master" and current_step != "agent":
                    continue
                chunk = data.get("chunk")
                if chunk is None:
                    continue
                # 兼容 chunk.content 是 str 或 list[dict]
                raw_content = getattr(chunk, "content", "") or ""
                if isinstance(raw_content, list):
                    # 某些多模态 LLM 把 content 编码为 list
                    text_pieces = []
                    for piece in raw_content:
                        if isinstance(piece, dict) and piece.get("type") == "text":
                            text_pieces.append(piece.get("text", ""))
                        elif isinstance(piece, str):
                            text_pieces.append(piece)
                    content = "".join(text_pieces)
                else:
                    content = str(raw_content)

                if content:
                    # 进入 TextMessage 段
                    if not in_text:
                        in_text = True
                        text_msg_id = f"msg-{uuid.uuid4().hex[:8]}"
                        yield sse("TextMessageStart", {"id": text_msg_id, "role": "assistant"})
                    # 输出增量
                    yield sse("TextMessageContent", {"id": text_msg_id, "content": content})

            # ---- 2.4 工具调用开始 ----
            elif kind == "on_tool_start":
                # 先关闭进行中的 TextMessage 段（保持协议状态机干净）
                if in_text:
                    yield sse("TextMessageEnd", {"id": text_msg_id})
                    in_text = False

                tool_name: str = name
                tool_input = data.get("input", {}) or {}
                # 统一 args 为字符串（前端 onToolCallArgs 期望 string 增量）
                if not isinstance(tool_input, str):
                    tool_input = json.dumps(tool_input, ensure_ascii=False)

                yield sse("ToolCallStart", {"name": tool_name, "args": tool_input})
                reasoning_steps.append({
                    "type": "tool_call",
                    "name": tool_name,
                    "args": tool_input,
                })

            # ---- 2.5 工具调用结束 ----
            elif kind == "on_tool_end":
                tool_name: str = name
                output = data.get("output", "")
                # 兼容 ToolMessage / str / dict / 其他对象
                if hasattr(output, "content"):
                    result_str = str(output.content)
                elif isinstance(output, (dict, list)):
                    result_str = json.dumps(output, ensure_ascii=False)
                else:
                    result_str = str(output)

                yield sse("ToolCallEnd", {
                    "name": tool_name,
                    "result": result_str[:2000],  # 限制长度避免单事件过大
                })
                reasoning_steps.append({
                    "type": "tool_result",
                    "name": tool_name,
                    "result": result_str[:500],
                })

            # ---- 2.6 其他事件忽略（on_chain_start 内部子链、on_llm_end 等） ----

        # ==========================================================
        # 3) 收尾：关闭可能仍打开的 TextMessage 段
        # ==========================================================
        if in_text:
            yield sse("TextMessageEnd", {"id": text_msg_id})
            in_text = False

        # ==========================================================
        # 4) 推理步骤聚合（流末尾一次性下发）
        # ==========================================================
        if reasoning_steps:
            yield sse("ReasoningSteps", {"steps": reasoning_steps})

        # ==========================================================
        # 5) 流正常结束
        # ==========================================================
        yield sse("RunFinished", {"status": "completed"})

    except Exception as e:
        # 异常路径：关闭可能打开的段 + 发送错误事件
        logger.error(f"流式响应错误: {e}", exc_info=True)
        if in_text:
            yield sse("TextMessageEnd", {"id": text_msg_id})
        yield sse("RunError", {"message": str(e)})


# ============================================================
# 主对话接口
# ============================================================


@router.get("/debug/tools")
async def debug_tools():
    """
    调试接口：返回当前进程 tool_manager 中所有工具的清单
    """
    from app.agent.nodes import tool_manager
    tools = tool_manager.get_all_tools()
    return {
        "count": len(tools),
        "names": [t.name for t in tools],
        "mcp_count": len(tool_manager._mcp_tools),
        "a2a_count": len(tool_manager._a2a_tools),
    }


@router.post("/chat")
async def chat(
    request: ChatRequest,
    mode: str = Query("single", description="模式: single(单Agent) / multi(多Agent协作) / master(统一大图)"),
    stream: bool = Query(False, description="是否流式响应: true(SSE流式) / false(阻塞，默认)")
):
    """
    基础对话接口
    
    支持三种模式：
    - single: 单 Agent 模式（默认）
    - multi: 多 Agent 协作模式
    - master: 统一大图模式（集成所有高级功能）
    
    Args:
        request: 对话请求（包含 message 和 conversation_id）
        mode: 运行模式（single / multi / master）
    
    Returns:
        ChatResponse: 对话响应
    """
    try:
        logger.info(f"收到对话请求: {request.message[:50]}... (模式: {mode}, 流式: {stream})")
        
        # 根据模式选择图和构建初始状态
        if mode == "master":
            graph = master_graph
            initial_state = {
                "messages": [HumanMessage(content=request.message)],
                "query": request.message,
                "conversation_id": request.conversation_id,
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
                # v2 防死循环新增字段
                "stuck_signature": None,
                "stuck_count": 0,
                "_force_skip_tools": False,
                "final_response": None,
            }
        
        elif mode == "multi":
            graph = multi_agent_graph
            initial_state = {
                "messages": [HumanMessage(content=request.message)],
                "next_agent": None,
                "final_result": None,
            }
        
        else:  # single
            graph = agent_graph
            initial_state = {
                "messages": [HumanMessage(content=request.message)],
                "tool_calls": [],
                "current_step": "start",
            }
        
        # 配置（用于记忆持久化 + 防死循环兜底）
        # ============================================================
        # recursion_limit 兜底说明（v2 防死循环第三层）：
        #   - 第一层：stuck_guard（业务层）—— 连续相同工具调用即拦截
        #   - 第二层：max_tool_calls（资源层）—— 累计调用次数上限
        #   - 第三层：recursion_limit（框架层）—— 哪怕前两层都失效，
        #     整张图的节点执行总步数也限制在 25 步内，绝不会无限循环
        # 25 步的估算：guard_input(1) + router(1) + agent(5) +
        #   stuck_guard(5) + human_review(5) + tools(5) + reflection(2)
        #   + guard_output(1) + summarizer(1) ≈ 25，留余量到 30
        # ============================================================
        config = {
            "configurable": {
                "thread_id": request.conversation_id
            },
            "recursion_limit": 30,
        }
        
        # ============================================================
        # 流式/阻塞 切换
        # ============================================================
        
        if stream:
            # 流式模式：返回 SSE 流
            logger.info("使用流式响应")
            return StreamingResponse(
                generate_stream_response(graph, initial_state, config, mode),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
                }
            )
        
        else:
            # 阻塞模式：等待完成后返回 JSON
            logger.info("使用阻塞响应")
            result = await graph.ainvoke(initial_state, config)
            
            # 根据模式提取响应和步骤
            if mode == "master":
                response_text = result.get("final_response") or "处理完成"
                tool_calls = list(result.get("tool_results", {}).keys())
                steps = extract_master_steps(result)
            
            elif mode == "multi":
                messages = result.get("messages", [])
                response_text = result.get("final_result") or (
                    messages[-1].content if messages else "抱歉，我没有理解。"
                )
                tool_calls = []
                steps = extract_multi_steps(result)
            
            else:  # single
                messages = result.get("messages", [])
                response_text = messages[-1].content if messages else "抱歉，我没有理解。"
                tool_calls = result.get("tool_calls", [])
                steps = extract_single_steps(result)
            
            return ChatResponse(
                response=response_text,
                conversation_id=request.conversation_id,
                tool_calls=tool_calls,
                steps=steps
            )
    
    except Exception as e:
        logger.error(f"对话处理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
