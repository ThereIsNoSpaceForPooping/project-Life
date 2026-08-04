"""
A2A Server 直接测试脚本（UTF-8 编码，避开 PowerShell GBK 问题）

测试场景：
1. 健康检查
2. 列出所有 Agent
3. 翻译任务：英文 → 中文
4. 查询任务结果
"""
import sys
import json
import httpx

BASE = "http://localhost:8002"
OUT = r"e:\008其他\桌面\WEB\project-Life\a2a_server\a2a_test_output.txt"


def log(msg: str):
    print(msg)
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def main():
    # 清空输出文件
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("")

    log("=" * 60)
    log("A2A Server 直接测试")
    log("=" * 60)

    # 1) 健康检查
    log("\n[1] 健康检查 GET /health")
    r = httpx.get(f"{BASE}/health", timeout=10.0)
    log(f"  状态码: {r.status_code}")
    log(f"  响应: {r.json()}")

    # 2) 列出 Agent
    log("\n[2] 列出 Agent GET /a2a/agents")
    r = httpx.get(f"{BASE}/a2a/agents", timeout=10.0)
    agents = r.json()
    log(f"  状态码: {r.status_code}")
    log(f"  Agent 数量: {len(agents)}")
    for a in agents:
        log(f"   - {a['name']:12s} | {a['description']} | capabilities={a['capabilities']}")

    # 3) 翻译任务
    log("\n[3] 翻译任务 POST /a2a/tasks")
    body = {
        "agent_name": "translator",
        "input_data": {
            "text": "Hello World, this is a direct A2A test from Python.",
            "source_lang": "auto",
            "target_lang": "Chinese",
        },
    }
    log(f"  请求体: {json.dumps(body, ensure_ascii=False, indent=2)}")
    r = httpx.post(f"{BASE}/a2a/tasks", json=body, timeout=60.0)
    log(f"  状态码: {r.status_code}")
    task = r.json()
    log(f"  任务 ID: {task['task_id']}")
    log(f"  状态: {task['status']}")

    # 4) 查询任务结果
    log("\n[4] 查询任务结果 GET /a2a/tasks/{task_id}")
    r = httpx.get(f"{BASE}/a2a/tasks/{task['task_id']}", timeout=10.0)
    result = r.json()
    log(f"  状态码: {r.status_code}")
    log(f"  状态: {result['status']}")
    if result.get("result"):
        log(f"  翻译结果:")
        log(f"    {result['result'].get('translation', '')}")
        log(f"  翻译说明:")
        log(f"    {result['result'].get('notes', '')}")

    # 5) 列出所有任务
    log("\n[5] 列出所有任务 GET /a2a/tasks")
    r = httpx.get(f"{BASE}/a2a/tasks?limit=5", timeout=10.0)
    tasks = r.json()
    log(f"  状态码: {r.status_code}")
    log(f"  总任务数: {tasks.get('total', 0)}")
    for t in tasks.get("tasks", [])[:5]:
        log(f"   - {t['id']} | {t['agent_name']:10s} | {t['status']:10s} | {t.get('created_at', '')}")

    log("\n" + "=" * 60)
    log("测试完成 ✅")
    log("=" * 60)


if __name__ == "__main__":
    main()
