/**
 * 聊天 API 模块
 * 提供与后端 Agent 通信的接口
 */

/**
 * 流式聊天接口
 * @param {Array} messages - 消息列表
 * @param {string} conversationId - 对话 ID
 * @param {Function} onChunk - 收到数据块的回调
 * @returns {Promise<void>}
 */
export async function chatStream(messages, conversationId, onChunk) {
  const response = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Conversation-ID': conversationId
    },
    body: JSON.stringify({
      messages,
      enable_tools: true
    })
  })

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() // 保留不完整的行

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6).trim()

        if (data === '[DONE]') continue

        try {
          const chunk = JSON.parse(data)
          onChunk(chunk)
        } catch (e) {
          console.error('Parse error:', e)
        }
      }
    }
  }
}

/**
 * 阻塞式聊天接口
 * @param {Array} messages - 消息列表
 * @param {string} conversationId - 对话 ID
 * @returns {Promise<Object>} 响应数据
 */
export async function chat(messages, conversationId) {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Conversation-ID': conversationId
    },
    body: JSON.stringify({
      messages,
      enable_tools: true
    })
  })

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }

  return response.json()
}
