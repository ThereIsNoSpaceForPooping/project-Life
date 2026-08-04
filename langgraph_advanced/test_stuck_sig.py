"""自检 stuck_guard 签名修复"""
import sys
from app.agent.middleware.stuck_guard import compute_tool_call_signature

# 模拟 LangChain 行为：每次 LLM 响应生成新的 tool_call_id
# 中文用 'cn_' 前缀避免 shell 转义问题
cn1 = "翻译：黄瓜"
cn2 = "翻译：苹果"
c1 = [{'id': 'call_001', 'name': 'a2a_translator', 'args': {'query': cn1}}]
c2 = [{'id': 'call_002', 'name': 'a2a_translator', 'args': {'query': cn1}}]
c3 = [{'id': 'call_003', 'name': 'a2a_translator', 'args': {'query': cn2}}]
s1 = compute_tool_call_signature(c1)
s2 = compute_tool_call_signature(c2)
s3 = compute_tool_call_signature(c3)
print('s1:', s1)
print('s2:', s2)
print('s3:', s3)
assert s1 == s2, '同 name+args 不同 id 应得相同签名'
assert s1 != s3, '不同 args 应得不同签名'
print('PASS: 签名稳定性 OK（id 已不参与签名）')
sys.exit(0)

