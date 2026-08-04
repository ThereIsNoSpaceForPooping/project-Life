<!--
  事件日志组件
  
  显示 AG-UI 协议的事件流
-->

<template>
  <div class="event-log">
    <div class="log-header">
      <h3>事件日志</h3>
      <button class="clear-btn" @click="handleClear" :disabled="events.length === 0">
        清空
      </button>
    </div>
    
    <div class="log-content" ref="logContentRef">
      <!-- 空状态 -->
      <div v-if="events.length === 0" class="empty-log">
        <div class="empty-icon">📋</div>
        <div class="empty-text">暂无事件</div>
      </div>
      
      <!-- 事件列表 -->
      <div 
        v-for="(event, index) in events" 
        :key="index" 
        class="event-item"
        :class="`event-${getEventType(event)}`"
      >
        <div class="event-time">{{ event.timestamp }}</div>
        <div class="event-type">
          <span class="type-badge">{{ getEventType(event) }}</span>
        </div>
        <div class="event-message">{{ formatMessage(event) }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * 事件日志逻辑
 */

import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  events: {
    type: Array,
    default: () => []
  }
})

// 日志内容引用
const logContentRef = ref(null)

// 获取事件类型
const getEventType = (event) => {
  if (event.type) return event.type
  if (event.message) return 'message'
  return 'unknown'
}

// 格式化消息
const formatMessage = (event) => {
  if (event.message) return event.message
  if (event.data) {
    if (typeof event.data === 'string') return event.data
    return JSON.stringify(event.data)
  }
  return ''
}

// 自动滚动到底部
watch(
  () => props.events,
  async () => {
    await nextTick()
    if (logContentRef.value) {
      logContentRef.value.scrollTop = logContentRef.value.scrollHeight
    }
  },
  { deep: true }
)

// 清空日志
const handleClear = () => {
  // 这里需要通过 emit 通知父组件清空
  // 暂时不实现，因为 events 是 props
}
</script>

<style scoped>
.event-log {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 头部 */
.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-md);
}

.log-header h3 {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.clear-btn {
  padding: 4px 12px;
  font-size: 0.75rem;
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  border-radius: var(--radius-sm);
  transition: all 0.2s;
}

.clear-btn:hover:not(:disabled) {
  background: var(--border-color);
}

.clear-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 内容 */
.log-content {
  flex: 1;
  overflow-y: auto;
  background: var(--bg-primary);
  border-radius: var(--radius-sm);
  padding: var(--spacing-sm);
}

/* 空状态 */
.empty-log {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-tertiary);
}

.empty-icon {
  font-size: 2rem;
  margin-bottom: var(--spacing-sm);
}

.empty-text {
  font-size: 0.875rem;
}

/* 事件项 */
.event-item {
  display: flex;
  gap: var(--spacing-sm);
  padding: var(--spacing-xs);
  border-bottom: 1px solid var(--border-color);
  font-size: 0.75rem;
  animation: slideIn 0.2s ease;
}

@keyframes slideIn {
  from { opacity: 0; transform: translateX(-10px); }
  to { opacity: 1; transform: translateX(0); }
}

.event-item:last-child {
  border-bottom: none;
}

.event-time {
  color: var(--text-tertiary);
  font-family: 'Courier New', monospace;
  flex-shrink: 0;
}

.event-type {
  flex-shrink: 0;
}

.type-badge {
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  font-size: 0.625rem;
  font-weight: 600;
  text-transform: uppercase;
}

/* 事件类型颜色 */
.event-run_started .type-badge,
.event-run_finished .type-badge {
  background: #dbeafe;
  color: #1e40af;
}

.event-text_start .type-badge,
.event-text_end .type-badge {
  background: #e0e7ff;
  color: #3730a3;
}

.event-tool_start .type-badge,
.event-tool_end .type-badge {
  background: #fef3c7;
  color: #92400e;
}

.event-step_start .type-badge,
.event-step_end .type-badge {
  background: #d1fae5;
  color: #065f46;
}

.event-error .type-badge {
  background: #fee2e2;
  color: #991b1b;
}

.event-user_message .type-badge {
  background: #f3e8ff;
  color: #6b21a8;
}

.event-cancel .type-badge {
  background: #fecaca;
  color: #991b1b;
}

.event-message {
  color: var(--text-primary);
  flex: 1;
  word-break: break-word;
  font-family: 'Courier New', monospace;
}
</style>
