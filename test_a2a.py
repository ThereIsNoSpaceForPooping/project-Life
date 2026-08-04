# -*- coding: utf-8 -*-
"""测试 A2A 工具调用"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests
import json

test_cases = [
    {
        "name": "研究任务 - 应触发 researcher",
        "message": "帮我研究一下人工智能的最新发展趋势",
        "expected_tool": "a2a_researcher"
    },
    {
        "name": "翻译任务 - 应触发 translator",
        "message": "把'你好世界'翻译成英文",
        "expected_tool": "a2a_translator"
    },
    {
        "name": "代码任务 - 应触发 coder",
        "message": "写一个 Python 快速排序算法",
        "expected_tool": "a2a_coder"
    },
    {
        "name": "分析任务 - 应触发 analyzer",
        "message": "分析这组数据的趋势：1, 3, 5, 7, 9, 11",
        "expected_tool": "a2a_analyzer"
    }
]

print("=" * 60)
print("A2A 工具调用测试")
print("=" * 60)

for i, test in enumerate(test_cases, 1):
    print(f"\n[{i}/4] {test['name']}")
    print(f"问题: {test['message']}")
    print(f"期望工具: {test['expected_tool']}")
    
    try:
        response = requests.post(
            "http://localhost:8005/chat",
            params={"mode": "master", "stream": "false"},
            json={
                "message": test['message'],
                "conversation_id": f"test-a2a-{i}"
            },
            timeout=60
        )
        
        result = response.json()
        print(f"响应: {result.get('response', '')[:100]}...")
        print(f"工具调用: {result.get('tool_calls', [])}")
        
        tool_calls = result.get('tool_calls', [])
        if any(test['expected_tool'] in str(tc) for tc in tool_calls):
            print(f"[OK] 成功: 调用了 {test['expected_tool']}")
        else:
            print(f"[FAIL] 未调用 {test['expected_tool']}")
            
    except Exception as e:
        print(f"[ERROR] {e}")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
