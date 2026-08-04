// -*- coding: utf-8 -*-
/**
 * AG-UI 客户端
 * 
 * 实现 AG-UI 协议，处理 SSE 事件流
 * 
 * AG-UI 协议事件类型：
 * - RunStarted: 运行开始
 * - RunFinished: 运行结束
 * - TextMessageStart: 文本消息开始
 * - TextMessageContent: 文本消息内容
 * - TextMessageEnd: 文本消息结束
 * - ToolCallStart: 工具调用开始
 * - ToolCallArgs: 工具调用参数
 * - ToolCallEnd: 工具调用结束
 * - StateDelta: 状态更新
 * - StepStarted: 步骤开始
 * - StepFinished: 步骤结束
 */

/**
 * AG-UI 客户端
 * 
 * 使用 fetch API 处理 SSE 流式响应
 * 注意：axios 在浏览器中不支持 ReadableStream，必须使用 fetch
 */

export class AGUIClient {
  /**
   * 构造函数
   * @param {string} baseUrl - 后端 API 基础 URL
   */
  constructor(baseUrl = '/api') {
    this.baseUrl = baseUrl
    this.abortController = null
  }
  
  /**
   * 发送聊天请求并处理 SSE 事件流
   * 
   * @param {Object} params - 请求参数
   * @param {string} params.message - 用户消息
   * @param {string} params.mode - 运行模式 (single/multi/master)
   * @param {string} params.conversation_id - 会话 ID
   * @param {Object} callbacks - 事件回调函数
   * @returns {Promise<void>}
   */
  async chat(params, callbacks) {
    // 创建 AbortController 用于取消请求
    this.abortController = new AbortController()
    
    const url = `${this.baseUrl}/chat?mode=${params.mode || 'master'}&stream=true`
    const conversationId = params.conversation_id || this.generateConversationId()
    
    try {
      // 使用 fetch API 发送 POST 请求，获取 SSE 流
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream'
        },
        body: JSON.stringify({
          message: params.message,
          conversation_id: conversationId
        }),
        signal: this.abortController.signal
      })
      
      // 检查响应状态
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      
      // 检查响应体是否为流
      if (!response.body) {
        throw new Error('响应体为空，不支持流式读取')
      }
      
      // 获取响应流读取器
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      
      // 读取 SSE 流
      while (true) {
        const { done, value } = await reader.read()
        
        if (done) {
          break
        }
        
        // 解码数据
        buffer += decoder.decode(value, { stream: true })
        
        // 按行分割
        const lines = buffer.split('\n')
        buffer = lines.pop() || '' // 保留最后一个不完整的行
        
        // 处理每一行
        for (const line of lines) {
          const trimmedLine = line.trim()
          
          if (trimmedLine.startsWith('data: ')) {
            const data = trimmedLine.slice(6)

            if (data === '[DONE]') {
              continue
            }

            try {
              const event = JSON.parse(data)
              this.handleEvent(event, callbacks)
            } catch (error) {
              console.warn('解析事件失败:', error, '原始数据:', data)
            }
          }
        }
      }

      // 修复 v3：移除冗余的 onRunFinished 兜底调用
      // 原因：后端 chat.py 已在 generate_stream_response 末尾 yield RunFinished 事件，
      //       这里再补一次会导致前端 onRunFinished 被触发 2 次（出现重复"run_finished"日志）。
      // 收尾完全由后端的 RunFinished 事件驱动，前端只负责转发，不要二次构造。

    } catch (error) {
      if (error.name === 'AbortError') {
        console.log('请求已取消')
      } else {
        console.error('聊天请求失败:', error)
        if (callbacks.onError) {
          callbacks.onError(error)
        }
      }
    }
  }
  
  /**
   * 处理 SSE 事件
   * 
   * @param {Object} event - 事件对象
   * @param {string} event.type - 事件类型
   * @param {Object} event.data - 事件数据
   * @param {Object} callbacks - 回调函数集合
   */
  handleEvent(event, callbacks) {
    const { type, data } = event
    
    switch (type) {
      case 'RunStarted':
        if (callbacks.onRunStarted) callbacks.onRunStarted(data)
        break
        
      case 'RunFinished':
        if (callbacks.onRunFinished) callbacks.onRunFinished(data)
        break
        
      case 'TextMessageStart':
        if (callbacks.onTextMessageStart) callbacks.onTextMessageStart(data)
        break
        
      case 'TextMessageContent':
        if (callbacks.onTextMessageContent) callbacks.onTextMessageContent(data)
        break
        
      case 'TextMessageEnd':
        if (callbacks.onTextMessageEnd) callbacks.onTextMessageEnd(data)
        break
        
      case 'ToolCallStart':
        if (callbacks.onToolCallStart) callbacks.onToolCallStart(data)
        break
        
      case 'ToolCallArgs':
        if (callbacks.onToolCallArgs) callbacks.onToolCallArgs(data)
        break
        
      case 'ToolCallEnd':
        if (callbacks.onToolCallEnd) callbacks.onToolCallEnd(data)
        break
        
      case 'StateDelta':
        if (callbacks.onStateDelta) callbacks.onStateDelta(data)
        break
        
      case 'StepStarted':
        if (callbacks.onStepStarted) callbacks.onStepStarted(data)
        break
        
      case 'StepFinished':
        if (callbacks.onStepFinished) callbacks.onStepFinished(data)
        break
        
      case 'ReasoningSteps':
      case 'reasoning_steps':
        if (callbacks.onReasoningSteps) callbacks.onReasoningSteps(data)
        break
        
      default:
        console.warn('未知事件类型:', type, data)
    }
  }
  
  /**
   * 取消当前请求
   */
  cancel() {
    if (this.abortController) {
      this.abortController.abort()
      this.abortController = null
    }
  }
  
  /**
   * 生成会话 ID
   * @returns {string} 会话 ID
   */
  generateConversationId() {
    return 'conv-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9)
  }
}
