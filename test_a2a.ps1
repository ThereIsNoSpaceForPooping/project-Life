# 测试 A2A 工具调用
$body = @{
    message = "帮我研究一下人工智能的最新发展趋势"
    conversation_id = "test-a2a-001"
} | ConvertTo-Json -Compress

$response = Invoke-RestMethod -Uri "http://localhost:8005/chat?mode=master" `
    -Method POST `
    -ContentType "application/json; charset=utf-8" `
    -Body ([System.Text.Encoding]::UTF8.GetBytes($body))

$response | ConvertTo-Json -Depth 10
