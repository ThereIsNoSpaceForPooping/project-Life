"""
AG-UI 协议流式事件验证脚本

测试：
1. 发起 SSE 流式请求
2. 解析每个 SSE 事件
3. 验证事件类型和字段结构符合 AG-UI 协议
4. 输出事件流摘要
"""
import sys
import json
import httpx

BASE = "http://localhost:8005"
OUT = r"e:\008其他\桌面\WEB\project-Life\langgraph_advanced\agui_verify_output.txt"

# 期望的事件类型（AG-UI 协议）
AGUI_EVENT_TYPES = {
    "RunStarted", "RunFinished", "RunError",
    "TextMessageStart", "TextMessageContent", "TextMessageEnd",
    "ToolCallStart", "ToolCallArgs", "ToolCallEnd",
    "StateDelta", "StepStarted", "StepFinished",
    "ReasoningSteps",
}

# 期望的旧事件类型（不应该再出现）
DEPRECATED_EVENT_TYPES = {
    "start", "end", "error", "token", "node_start", "node_end",
    "tool_call", "tool_result", "reasoning_steps",
}


def log(msg: str):
    print(msg)
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def main():
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("")

    log("=" * 70)
    log("AG-UI 协议流式事件验证")
    log("=" * 70)

    # 构造请求
    # 说明：前端 vite proxy 把 /api 前缀去掉，所以后端真实路径是 /chat
    url = f"{BASE}/chat?mode=master&stream=true"
    body = {
        "message": "读取 README.md",
        "conversation_id": "agui-mcp-final-001",
    }
    log("  (期望: router 关键词'读取'命中 → force_tool=mcp_file_read → agent 调 mcp_file_read)")
    log(f"\n[请求] POST {url}")
    log(f"  body: {json.dumps(body, ensure_ascii=False)}")
    log("  (此请求预期会触发 a2a_translator 工具调用，验证 ToolCallStart/End)")

    # 收集事件
    events_received: list[dict] = []
    event_type_counts: dict[str, int] = {}
    text_content: str = ""
    tool_calls: list[dict] = []
    steps: list[str] = []

    try:
        with httpx.stream("POST", url, json=body, timeout=120.0) as resp:
            log(f"\n[响应] 状态码: {resp.status_code}")
            log(f"  Content-Type: {resp.headers.get('content-type', 'N/A')}")

            buffer = ""
            for raw_line in resp.iter_lines():
                if not raw_line:
                    continue
                line = raw_line.strip()
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    continue

                try:
                    event = json.loads(data_str)
                except json.JSONDecodeError as e:
                    log(f"  [WARN] 事件 JSON 解析失败: {data_str[:100]}")
                    continue

                events_received.append(event)
                etype = event.get("type", "<unknown>")
                event_type_counts[etype] = event_type_counts.get(etype, 0) + 1

                # 按事件类型累计关键信息
                e_data = event.get("data") or {}
                if etype == "TextMessageContent":
                    text_content += e_data.get("content", "")
                elif etype == "ToolCallStart":
                    tool_calls.append({
                        "name": e_data.get("name"),
                        "args": e_data.get("args", "")[:200],
                    })
                elif etype == "StepStarted":
                    steps.append(e_data.get("name", ""))

                # 显示前 30 个事件 + 工具相关事件
                if len(events_received) <= 5 or "ool" in etype:
                    log(f"  [{etype}] data={json.dumps(e_data, ensure_ascii=False)[:150]}")

    except Exception as e:
        log(f"\n[ERROR] 请求失败: {e}")
        import traceback
        log(traceback.format_exc())
        return

    # ============================================================
    # 验证结果
    # ============================================================
    log("\n" + "=" * 70)
    log("验证结果")
    log("=" * 70)

    # 1) 事件类型统计
    log(f"\n[1] 总事件数: {len(events_received)}")
    log(f"    类型分布: {event_type_counts}")

    # 2) 检查是否还使用旧事件类型
    deprecated_found = [t for t in event_type_counts if t in DEPRECATED_EVENT_TYPES]
    if deprecated_found:
        log(f"\n[FAIL] 发现旧事件类型: {deprecated_found}")
    else:
        log("\n[PASS] 无旧事件类型残留")

    # 3) 检查所有事件是否都符合 AG-UI 标准
    unknown_types = [t for t in event_type_counts if t not in AGUI_EVENT_TYPES]
    if unknown_types:
        log(f"[WARN] 发现未在 AG-UI 白名单的事件类型: {unknown_types}")
    else:
        log("[PASS] 所有事件类型都在 AG-UI 协议白名单内")

    # 4) 关键事件必现性
    required_types = {"RunStarted", "RunFinished"}
    missing = required_types - event_type_counts.keys()
    if missing:
        log(f"[FAIL] 缺失关键事件: {missing}")
    else:
        log(f"[PASS] 关键事件齐全 (RunStarted, RunFinished)")

    # 5) 验证事件结构
    struct_errors = []
    for i, evt in enumerate(events_received):
        # 必须有 type 字段
        if "type" not in evt:
            struct_errors.append(f"  事件 #{i} 缺 type 字段")
            continue
        # 有 type 但有 data 时 data 必须是 dict
        if "data" in evt and not isinstance(evt["data"], dict):
            struct_errors.append(f"  事件 #{i} ({evt['type']}) data 不是 dict")
    if struct_errors:
        log("\n[FAIL] 事件结构错误:")
        for e in struct_errors:
            log(e)
    else:
        log("\n[PASS] 所有事件结构都符合 {\"type\": ..., \"data\": {...}} 格式")

    # 6) 关键字段验证
    field_errors = []
    for evt in events_received:
        et = evt.get("type")
        ed = evt.get("data", {}) or {}
        if et == "TextMessageContent" and "content" not in ed:
            field_errors.append(f"TextMessageContent 缺 content 字段")
        if et == "ToolCallStart" and "name" not in ed:
            field_errors.append(f"ToolCallStart 缺 name 字段")
        if et == "ToolCallEnd" and "name" not in ed:
            field_errors.append(f"ToolCallEnd 缺 name 字段")
        if et == "StepStarted" and "name" not in ed:
            field_errors.append(f"StepStarted 缺 name 字段")
    if field_errors:
        log(f"\n[FAIL] 字段错误: {field_errors[:5]}")
    else:
        log("[PASS] 所有关键事件的字段结构正确")

    # 7) 业务内容摘要
    log("\n[摘要] LLM 文本输出（累积）:")
    log(f"  {text_content[:500]}")
    if len(text_content) > 500:
        log(f"  ... (共 {len(text_content)} 字符)")

    log(f"\n[摘要] 工具调用: {len(tool_calls)} 次")
    for tc in tool_calls:
        log(f"   - {tc['name']}: {tc['args'][:100]}")

    log(f"\n[摘要] 步骤执行: {steps}")

    log("\n" + "=" * 70)
    log("验证结束")
    log("=" * 70)


if __name__ == "__main__":
    main()
