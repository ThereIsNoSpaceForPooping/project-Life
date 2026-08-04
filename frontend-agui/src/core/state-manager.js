// -*- coding: utf-8 -*-
/**
 * 状态管理器
 * 
 * 管理应用的全局状态，包括：
 * - 消息列表
 * - 当前运行状态
 * - 工具调用状态
 * - 会话信息
 */

export class StateManager {
  constructor() {
    // 消息列表
    this.messages = []
    
    // 当前运行状态
    this.isRunning = false
    
    // 当前会话 ID
    this.conversationId = this.generateConversationId()
    
    // 当前工具调用
    this.currentToolCall = null
    
    // 状态监听器
    this.listeners = new Map()
  }
  
  /**
   * 添加消息
   * @param {Object} message - 消息对象
   */
  addMessage(message) {
    this.messages.push(message)
    this.notify('messages:changed', this.messages)
  }
  
  /**
   * 更新最后一条消息
   * @param {Function} updater - 更新函数
   */
  updateLastMessage(updater) {
    if (this.messages.length > 0) {
      const lastMessage = this.messages[this.messages.length - 1]
      updater(lastMessage)
      this.notify('messages:changed', this.messages)
    }
  }
  
  /**
   * 设置运行状态
   * @param {boolean} isRunning - 是否运行中
   */
  setRunning(isRunning) {
    this.isRunning = isRunning
    this.notify('running:changed', isRunning)
  }
  
  /**
   * 设置当前工具调用
   * @param {Object} toolCall - 工具调用对象
   */
  setCurrentToolCall(toolCall) {
    this.currentToolCall = toolCall
    this.notify('toolCall:changed', toolCall)
  }
  
  /**
   * 重置会话
   */
  resetConversation() {
    this.messages = []
    this.isRunning = false
    this.conversationId = this.generateConversationId()
    this.currentToolCall = null
    this.notify('conversation:reset', null)
  }
  
  /**
   * 订阅状态变化
   * @param {string} event - 事件名称
   * @param {Function} callback - 回调函数
   * @returns {Function} 取消订阅函数
   */
  subscribe(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set())
    }
    
    this.listeners.get(event).add(callback)
    
    // 返回取消订阅函数
    return () => {
      this.listeners.get(event).delete(callback)
    }
  }
  
  /**
   * 通知状态变化
   * @param {string} event - 事件名称
   * @param {any} data - 数据
   */
  notify(event, data) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).forEach(callback => {
        try {
          callback(data)
        } catch (error) {
          console.error('状态监听器执行失败:', error)
        }
      })
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
