// -*- coding: utf-8 -*-
/**
 * 聊天服务
 * 
 * 封装与后端的聊天交互逻辑
 */

import { AGUIClient } from '../core/agui-client.js'

export class ChatService {
  constructor() {
    // 创建 AG-UI 客户端
    this.client = new AGUIClient('/api')
    
    // 当前运行状态
    this.isRunning = false
    
    // 事件回调
    this.callbacks = {}
  }
  
  /**
   * 发送消息
   * 
   * @param {string} message - 用户消息
   * @param {string} mode - 运行模式 (single/multi/master)
   * @param {string} conversationId - 会话 ID
   * @param {Object} callbacks - 事件回调函数
   * 
   * @returns {Promise<void>}
   */
  async sendMessage(message, mode = 'master', conversationId = null, callbacks = {}) {
    if (this.isRunning) {
      throw new Error('当前正在运行中，请等待完成')
    }
    
    this.isRunning = true
    this.callbacks = callbacks
    
    try {
      await this.client.chat(
        {
          message,
          mode,
          conversation_id: conversationId
        },
        {
          onRunStarted: (data) => {
            if (callbacks.onRunStarted) callbacks.onRunStarted(data)
          },
          
          onRunFinished: (data) => {
            this.isRunning = false
            if (callbacks.onRunFinished) callbacks.onRunFinished(data)
          },
          
          onTextMessageStart: (data) => {
            if (callbacks.onTextMessageStart) callbacks.onTextMessageStart(data)
          },
          
          onTextMessageContent: (data) => {
            if (callbacks.onTextMessageContent) callbacks.onTextMessageContent(data)
          },
          
          onTextMessageEnd: (data) => {
            if (callbacks.onTextMessageEnd) callbacks.onTextMessageEnd(data)
          },
          
          onToolCallStart: (data) => {
            if (callbacks.onToolCallStart) callbacks.onToolCallStart(data)
          },
          
          onToolCallArgs: (data) => {
            if (callbacks.onToolCallArgs) callbacks.onToolCallArgs(data)
          },
          
          onToolCallEnd: (data) => {
            if (callbacks.onToolCallEnd) callbacks.onToolCallEnd(data)
          },
          
          onStateDelta: (data) => {
            if (callbacks.onStateDelta) callbacks.onStateDelta(data)
          },
          
          onStepStarted: (data) => {
            if (callbacks.onStepStarted) callbacks.onStepStarted(data)
          },
          
          onStepFinished: (data) => {
            if (callbacks.onStepFinished) callbacks.onStepFinished(data)
          },
          
          onReasoningSteps: (data) => {
            if (callbacks.onReasoningSteps) callbacks.onReasoningSteps(data)
          },
          
          onError: (error) => {
            this.isRunning = false
            if (callbacks.onError) callbacks.onError(error)
          }
        }
      )
    } catch (error) {
      this.isRunning = false
      throw error
    }
  }
  
  /**
   * 取消当前请求
   */
  cancel() {
    this.client.cancel()
    this.isRunning = false
  }
  
  /**
   * 获取运行状态
   * @returns {boolean} 是否运行中
   */
  getIsRunning() {
    return this.isRunning
  }
}
