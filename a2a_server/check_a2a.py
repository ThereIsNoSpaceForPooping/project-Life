"""检查 A2A Server 健康状态、Agent 列表、并实跑一次翻译"""
import httpx
import json
import sys

BASE = "http://localhost:8002"

print("=" * 70)
print("A2A Server 检查")
print("=" * 70)

# 1) /health
print("\n[1] /health")
try:
    r = httpx.get(f"{BASE}/health", timeout=5)
    print(f"  status: {r.status_code}")
    print(f"  body  : {r.text}")
except Exception as e:
    print(f"  ERROR : {e}")
    sys.exit(1)

# 2) /a2a/agents
print("\n[2] /a2a/agents")
try:
    r = httpx.get(f"{BASE}/a2a/agents", timeout=5)
    print(f"  status: {r.status_code}")
    agents = r.json()
    if isinstance(agents, list):
        print(f"  count : {len(agents)}")
        for a in agents:
            print(f"    - {a.get('name'):12s} | {a.get('description', '')[:50]}")
            caps = a.get("capabilities", [])
            if caps:
                print(f"      caps: {caps}")
    else:
        print(json.dumps(agents, ensure_ascii=False, indent=2))
except Exception as e:
    print(f"  ERROR : {e}")
    sys.exit(1)

# 3) 实跑翻译
print("\n[3] 实跑翻译（POST /a2a/tasks）")
if isinstance(agents, list) and any(a.get("name") == "translator" for a in agents):
    try:
        # 模拟 agent 用翻译工具时的真实请求
        payload = {
            "agent_name": "translator",
            "input_data": {
                "text": "使用翻译工具，翻译 香蕉",
                "source_lang": "auto",
                "target_lang": "英文",
            },
        }
        r = httpx.post(f"{BASE}/a2a/tasks", json=payload, timeout=60)
        print(f"  status: {r.status_code}")
        try:
            print(json.dumps(r.json(), ensure_ascii=False, indent=2)[:2000])
        except Exception:
            print(r.text[:2000])
    except Exception as e:
        print(f"  ERROR : {e}")
else:
    print("  SKIP  : 没有 translator agent")

print("\n" + "=" * 70)
print("Done.")
