<!--
  聊天窗口组件
  
  整合消息列表和输入框，处理聊天逻辑
-->

<template>
  <div class="chat-window">
    <MessageList :messages="messages" :is-running="isRunning" />
    <MessageInput 
      :is-running="isRunning"
      @send="handleSend"
      @cancel="handleCancel"
    />
  </div>
</template>

<script setup>
/**
 * 聊天窗口逻辑
 */

import { ref, inject, onMounted } from 'vue'
import MessageList from './MessageList.vue'
import MessageInput from './MessageInput.vue'
import { ChatService } from '../services/chat-service.js'

// 注入全局状态
const stateManager = inject('stateManager')
const addEvent = inject('addEvent')
const updateAgentStatus = inject('updateAgentStatus')

// 聊天服务
const chatService = new ChatService()

// 消息列表
const messages = ref([])

// 运行状态
const isRunning = ref(false)

// 当前会话 ID
const conversationId = ref('conv-' + Date.now())

// 当前消息 ID
let messageIdCounter = 0

// 处理发送消息
const handleSend = async ({ message, mode }) => {
  if (!message.trim() || isRunning.value) return
  
  // 添加用户消息
  const userMessage = {
    id: ++messageIdCounter,
    role: 'user',
    content: message,
    timestamp: new Date().toLocaleTimeString()
  }
  messages.value.push(userMessage)
  
  // 添加 AI 消息占位
  const aiMessage = {
    id: ++messageIdCounter,
    role: 'assistant',
    content: '',
    timestamp: new Date().toLocaleTimeString(),
    toolCalls: [],
    steps: []
  }
  messages.value.push(aiMessage)
  
  // 更新状态
  isRunning.value = true
  updateAgentStatus({ isRunning: true, progress: 0 })
  
  // 记录事件
  addEvent({
    type: 'user_message',
    message: message.substring(0, 50) + (message.length > 50 ? '...' : '')
  })
  
  try {
    // 发送请求
    await chatService.sendMessage(message, mode, conversationId.value, {
      // 运行开始
      onRunStarted: (data) => {
        addEvent({ type: 'run_started', data })
        updateAgentStatus({ currentStep: '开始执行' })
      },
      
      // 文本消息开始
      onTextMessageStart: (data) => {
        addEvent({ type: 'text_start', data })
      },
      
      // 文本消息内容
      onTextMessageContent: (data) => {
        // 更新最后一条 AI 消息
        const lastAiMsg = messages.value.filter(m => m.role === 'assistant').pop()
        if (lastAiMsg) {
          lastAiMsg.content += data.content || ''
        }
      },
      
      // 文本消息结束
      onTextMessageEnd: (data) => {
        addEvent({ type: 'text_end', data })
      },
      
      // 工具调用开始
      onToolCallStart: (data) => {
        addEvent({ type: 'tool_start', data })
        
        const lastAiMsg = messages.value.filter(m => m.role === 'assistant').pop()
        if (lastAiMsg) {
          lastAiMsg.toolCalls.push({
            name: data.name,
            args: '',
            result: null,
            status: 'running'
          })
        }
        
        updateAgentStatus({ currentStep: `调用工具: ${data.name}` })
      },
      
      // 工具调用参数
      onToolCallArgs: (data) => {
        const lastAiMsg = messages.value.filter(m => m.role === 'assistant').pop()
        if (lastAiMsg && lastAiMsg.toolCalls.length > 0) {
          const lastTool = lastAiMsg.toolCalls[lastAiMsg.toolCalls.length - 1]
          lastTool.args += data.args || ''
        }
      },
      
      // 工具调用结束
      onToolCallEnd: (data) => {
        addEvent({ type: 'tool_end', data })
        
        const lastAiMsg = messages.value.filter(m => m.role === 'assistant').pop()
        if (lastAiMsg && lastAiMsg.toolCalls.length > 0) {
          const lastTool = lastAiMsg.toolCalls[lastAiMsg.toolCalls.length - 1]
          lastTool.status = 'completed'
          lastTool.result = data.result
        }
      },
      
      // 步骤开始
      onStepStarted: (data) => {
        addEvent({ type: 'step_start', data })
        
        const lastAiMsg = messages.value.filter(m => m.role === 'assistant').pop()
        if (lastAiMsg) {
          lastAiMsg.steps.push({
            name: data.name,
            status: 'running',
            startTime: new Date().toLocaleTimeString()
          })
        }
        
        updateAgentStatus({ currentStep: data.name })
      },
      
      // 步骤结束
      onStepFinished: (data) => {
        addEvent({ type: 'step_end', data })
        
        const lastAiMsg = messages.value.filter(m => m.role === 'assistant').pop()
        if (lastAiMsg && lastAiMsg.steps.length > 0) {
          const lastStep = lastAiMsg.steps[lastAiMsg.steps.length - 1]
          lastStep.status = 'completed'
          lastStep.endTime = new Date().toLocaleTimeString()
        }
      },
      
      // 推理步骤详情
      onReasoningSteps: (data) => {
        addEvent({ type: 'reasoning_steps', data })
        
        const lastAiMsg = messages.value.filter(m => m.role === 'assistant').pop()
        if (lastAiMsg && data.steps) {
          // 将推理步骤添加到消息中
          lastAiMsg.reasoningSteps = data.steps
        }
      },
      
      // 运行结束
      onRunFinished: (data) => {
        addEvent({ type: 'run_finished', data })
        
        isRunning.value = false
        updateAgentStatus({ 
          isRunning: false, 
          currentStep: null,
          progress: 100
        })
      },
      
      // 错误处理
      onError: (error) => {
        addEvent({ type: 'error', message: error.message })
        
        const lastAiMsg = messages.value.filter(m => m.role === 'assistant').pop()
        if (lastAiMsg) {
          lastAiMsg.content = `错误: ${error.message}`
          lastAiMsg.error = true
        }
        
        isRunning.value = false
        updateAgentStatus({ isRunning: false, currentStep: null })
      }
    })
  } catch (error) {
    console.error('发送消息失败:', error)
    addEvent({ type: 'error', message: error.message })
    isRunning.value = false
    updateAgentStatus({ isRunning: false, currentStep: null })
  }
}

// 处理取消
const handleCancel = () => {
  chatService.cancel()
  isRunning.value = false
  updateAgentStatus({ isRunning: false, currentStep: null })
  addEvent({ type: 'cancel', message: '用户取消请求' })
}

// 暴露方法给父组件
defineExpose({
  messages,
  clearMessages: () => {
    messages.value = []
    conversationId.value = 'conv-' + Date.now()
  }
})
</script>

<style scoped>
.chat-window {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-primary);
}
</style>
