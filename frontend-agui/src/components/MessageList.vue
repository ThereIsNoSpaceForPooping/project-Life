<!--
  消息列表组件
  
  显示所有聊天消息
-->

<template>
  <div class="message-list" ref="messageListRef">
    <!-- 空状态 -->
    <div v-if="messages.length === 0" class="empty-state">
      <div class="empty-icon">💬</div>
      <p class="empty-text">开始对话吧！</p>
      <p class="empty-hint">输入消息，AI 将通过 MCP 和 A2A 为您服务</p>
    </div>
    
    <!-- 消息列表 -->
    <div 
      v-for="message in messages" 
      :key="message.id" 
      class="message"
      :class="[`message-${message.role}`, { 'message-error': message.error }]"
    >
      <!-- 头像 -->
      <div class="message-avatar">
        <span v-if="message.role === 'user'">👤</span>
        <span v-else>🤖</span>
      </div>
      
      <!-- 消息内容 -->
      <div class="message-content">
        <!-- 角色标签 -->
        <div class="message-header">
          <span class="message-role">
            {{ message.role === 'user' ? '您' : 'AI 助手' }}
          </span>
          <span class="message-time">{{ message.timestamp }}</span>
        </div>
        
        <!-- 文本内容 -->
        <div class="message-text" v-if="message.content">
          {{ message.content }}
          <span v-if="message.role === 'assistant' && isRunning && message === lastAiMessage" class="typing-indicator">▊</span>
        </div>
        
        <!-- 加载状态 -->
        <div v-if="message.role === 'assistant' && !message.content && isRunning" class="message-loading">
          <span class="loading-dot"></span>
          <span class="loading-dot"></span>
          <span class="loading-dot"></span>
        </div>
        
        <!-- 工具调用 -->
        <div v-if="message.toolCalls && message.toolCalls.length > 0" class="tool-calls">
          <ToolCallCard 
            v-for="(tool, index) in message.toolCalls" 
            :key="index"
            :tool-call="tool"
          />
        </div>
        
        <!-- 推理步骤详情 -->
        <div v-if="message.reasoningSteps && message.reasoningSteps.length > 0" class="reasoning-steps">
          <div class="steps-header">
            <span class="steps-icon">🔍</span>
            <span class="steps-title">推理过程</span>
          </div>
          
          <div class="steps-container">
            <div 
              v-for="(step, index) in message.reasoningSteps" 
              :key="index"
              class="step-item"
              :class="`step-type-${step.type}`"
            >
              <!-- Agent 推理步骤 -->
              <div v-if="step.type === 'agent_reasoning'" class="step-content">
                <div class="step-header">
                  <span class="step-icon">🤖</span>
                  <span class="step-label">Agent 推理</span>
                </div>
                <div class="step-detail">{{ step.content }}</div>
              </div>
              
              <!-- 工具调用步骤 -->
              <div v-else-if="step.type === 'tool_call'" class="step-content">
                <div class="step-header">
                  <span class="step-icon">🔧</span>
                  <span class="step-label">调用工具: {{ step.tool_name }}</span>
                </div>
                <div class="step-detail">
                  <code class="tool-args">{{ JSON.stringify(step.tool_args, null, 2) }}</code>
                </div>
              </div>
              
              <!-- 工具结果步骤 -->
              <div v-else-if="step.type === 'tool_result'" class="step-content">
                <div class="step-header">
                  <span class="step-icon">✅</span>
                  <span class="step-label">工具 {{ step.tool_name }} 返回</span>
                </div>
                <div class="step-detail">
                  <pre class="tool-result">{{ step.tool_result }}</pre>
                </div>
              </div>
              
              <!-- 最终回答步骤 -->
              <div v-else-if="step.type === 'final_answer'" class="step-content">
                <div class="step-header">
                  <span class="step-icon">💡</span>
                  <span class="step-label">最终回答</span>
                </div>
                <div class="step-detail">{{ step.content }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * 消息列表逻辑
 */

import { ref, computed, watch, nextTick } from 'vue'
import ToolCallCard from './ToolCallCard.vue'

const props = defineProps({
  messages: {
    type: Array,
    default: () => []
  },
  isRunning: {
    type: Boolean,
    default: false
  }
})

// 消息列表引用
const messageListRef = ref(null)

// 最后一条 AI 消息
const lastAiMessage = computed(() => {
  const aiMessages = props.messages.filter(m => m.role === 'assistant')
  return aiMessages[aiMessages.length - 1]
})

// 自动滚动到底部
watch(
  () => props.messages,
  async () => {
    await nextTick()
    if (messageListRef.value) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight
    }
  },
  { deep: true }
)
</script>

<style scoped>
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-lg);
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-secondary);
}

.empty-icon {
  font-size: 3rem;
  margin-bottom: var(--spacing-md);
}

.empty-text {
  font-size: 1.125rem;
  margin-bottom: var(--spacing-sm);
}

.empty-hint {
  font-size: 0.875rem;
  color: var(--text-tertiary);
}

/* 消息项 */
.message {
  display: flex;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* 用户消息 */
.message-user {
  flex-direction: row-reverse;
}

.message-user .message-content {
  background: var(--primary-color);
  color: white;
  border-radius: var(--radius-lg) var(--radius-lg) 0 var(--radius-lg);
}

.message-user .message-header {
  flex-direction: row-reverse;
}

.message-user .message-role,
.message-user .message-time {
  color: rgba(255, 255, 255, 0.8);
}

/* AI 消息 */
.message-assistant .message-content {
  background: var(--bg-secondary);
  border-radius: var(--radius-lg) var(--radius-lg) var(--radius-lg) 0;
}

/* 错误消息 */
.message-error .message-content {
  background: #fef2f2;
  border: 1px solid var(--error-color);
}

/* 头像 */
.message-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--bg-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.25rem;
  flex-shrink: 0;
}

/* 消息内容 */
.message-content {
  max-width: 70%;
  padding: var(--spacing-md);
}

/* 消息头部 */
.message-header {
  display: flex;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-xs);
  font-size: 0.75rem;
}

.message-role {
  font-weight: 500;
}

.message-time {
  color: var(--text-tertiary);
}

/* 消息文本 */
.message-text {
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

/* 打字指示器 */
.typing-indicator {
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

/* 加载动画 */
.message-loading {
  display: flex;
  gap: 4px;
  padding: var(--spacing-sm) 0;
}

.loading-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-tertiary);
  animation: bounce 1.4s infinite ease-in-out;
}

.loading-dot:nth-child(1) { animation-delay: -0.32s; }
.loading-dot:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

/* 工具调用 */
.tool-calls {
  margin-top: var(--spacing-md);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

/* 推理步骤 */
.reasoning-steps {
  margin-top: var(--spacing-md);
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--border-color);
}

.steps-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  margin-bottom: var(--spacing-sm);
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-secondary);
}

.steps-icon {
  font-size: 1rem;
}

.steps-container {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.step-item {
  padding: var(--spacing-sm);
  border-radius: var(--radius-md);
  background: var(--bg-primary);
  border-left: 3px solid var(--border-color);
}

.step-type-agent_reasoning {
  border-left-color: var(--primary-color);
}

.step-type-tool_call {
  border-left-color: var(--warning-color);
}

.step-type-tool_result {
  border-left-color: var(--success-color);
}

.step-type-final_answer {
  border-left-color: var(--info-color);
}

.step-content {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.step-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  font-size: 0.8125rem;
  font-weight: 500;
}

.step-icon {
  font-size: 0.875rem;
}

.step-label {
  color: var(--text-primary);
}

.step-detail {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  line-height: 1.5;
  padding-left: 1.5rem;
}

.tool-args {
  display: block;
  padding: var(--spacing-xs);
  background: var(--bg-tertiary);
  border-radius: var(--radius-sm);
  font-size: 0.75rem;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.tool-result {
  display: block;
  padding: var(--spacing-xs);
  background: var(--bg-tertiary);
  border-radius: var(--radius-sm);
  font-size: 0.75rem;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow-y: auto;
  margin: 0;
}
</style>
