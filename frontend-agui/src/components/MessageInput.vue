<!--
  消息输入组件
  
  处理用户输入和发送
-->

<template>
  <div class="message-input">
    <!-- 模式选择 -->
    <div class="mode-selector">
      <button 
        v-for="m in modes" 
        :key="m.value"
        class="mode-btn"
        :class="{ active: selectedMode === m.value }"
        @click="selectedMode = m.value"
      >
        {{ m.label }}
      </button>
    </div>
    
    <!-- 输入区域 -->
    <div class="input-area">
      <textarea
        ref="textareaRef"
        v-model="inputMessage"
        placeholder="输入消息... (Enter 发送, Shift+Enter 换行)"
        :disabled="isRunning"
        @keydown="handleKeydown"
        rows="1"
      ></textarea>
      
      <!-- 发送/取消按钮 -->
      <button 
        class="send-btn"
        :class="{ running: isRunning }"
        @click="handleSubmit"
        :disabled="!canSend"
      >
        <span v-if="isRunning">⬛</span>
        <span v-else>➤</span>
      </button>
    </div>
    
    <!-- 提示文字 -->
    <div class="input-hint">
      <span v-if="isRunning">正在处理中...</span>
      <span v-else>当前模式: {{ currentModeLabel }}</span>
    </div>
  </div>
</template>

<script setup>
/**
 * 消息输入逻辑
 */

import { ref, computed } from 'vue'

const props = defineProps({
  isRunning: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['send', 'cancel'])

// 输入的消息
const inputMessage = ref('')

// 选择的模式
const selectedMode = ref('master')

// 文本框引用
const textareaRef = ref(null)

// 模式列表
const modes = [
  { value: 'single', label: '单 Agent' },
  { value: 'multi', label: '多 Agent' },
  { value: 'master', label: '统一大图' }
]

// 当前模式标签
const currentModeLabel = computed(() => {
  return modes.find(m => m.value === selectedMode.value)?.label || ''
})

// 是否可以发送
const canSend = computed(() => {
  if (props.isRunning) return true // 运行时显示取消按钮
  return inputMessage.value.trim().length > 0
})

// 处理按键
const handleKeydown = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSubmit()
  }
}

// 处理提交
const handleSubmit = () => {
  if (props.isRunning) {
    // 运行时点击取消
    emit('cancel')
  } else {
    // 发送消息
    const message = inputMessage.value.trim()
    if (message) {
      emit('send', { message, mode: selectedMode.value })
      inputMessage.value = ''
      
      // 重置文本框高度
      if (textareaRef.value) {
        textareaRef.value.style.height = 'auto'
      }
    }
  }
}
</script>

<style scoped>
.message-input {
  padding: var(--spacing-md);
  border-top: 1px solid var(--border-color);
  background: var(--bg-secondary);
}

/* 模式选择器 */
.mode-selector {
  display: flex;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-md);
}

.mode-btn {
  padding: var(--spacing-xs) var(--spacing-md);
  border-radius: var(--radius-md);
  font-size: 0.875rem;
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  transition: all 0.2s;
}

.mode-btn:hover {
  background: var(--border-color);
}

.mode-btn.active {
  background: var(--primary-color);
  color: white;
}

/* 输入区域 */
.input-area {
  display: flex;
  gap: var(--spacing-sm);
  align-items: flex-end;
}

textarea {
  flex: 1;
  resize: none;
  min-height: 44px;
  max-height: 120px;
  padding: var(--spacing-sm) var(--spacing-md);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  background: var(--bg-primary);
  font-size: 0.875rem;
  line-height: 1.5;
  transition: border-color 0.2s;
}

textarea:focus {
  border-color: var(--primary-color);
}

textarea:disabled {
  background: var(--bg-tertiary);
  cursor: not-allowed;
}

/* 发送按钮 */
.send-btn {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--primary-color);
  color: white;
  font-size: 1.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  flex-shrink: 0;
}

.send-btn:hover:not(:disabled) {
  background: var(--primary-hover);
  transform: scale(1.05);
}

.send-btn:disabled {
  background: var(--border-color);
  cursor: not-allowed;
}

.send-btn.running {
  background: var(--error-color);
}

.send-btn.running:hover {
  background: #dc2626;
}

/* 提示文字 */
.input-hint {
  margin-top: var(--spacing-sm);
  font-size: 0.75rem;
  color: var(--text-tertiary);
  text-align: center;
}
</style>
