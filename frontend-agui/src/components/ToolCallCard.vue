<!--
  工具调用卡片组件
  
  显示工具调用的详细信息
-->

<template>
  <div class="tool-call-card" :class="`status-${toolCall.status}`">
    <!-- 头部 -->
    <div class="card-header">
      <div class="tool-icon">
        <span v-if="toolCall.status === 'running'">⏳</span>
        <span v-else-if="toolCall.status === 'completed'">✓</span>
        <span v-else>⚠</span>
      </div>
      <div class="tool-name">{{ toolCall.name }}</div>
      <div class="tool-status">{{ statusText }}</div>
    </div>
    
    <!-- 参数 -->
    <div v-if="toolCall.args" class="card-section">
      <div class="section-title">参数</div>
      <pre class="section-content">{{ formatArgs(toolCall.args) }}</pre>
    </div>
    
    <!-- 结果 -->
    <div v-if="toolCall.result" class="card-section">
      <div class="section-title">结果</div>
      <pre class="section-content">{{ formatResult(toolCall.result) }}</pre>
    </div>
  </div>
</template>

<script setup>
/**
 * 工具调用卡片逻辑
 */

import { computed } from 'vue'

const props = defineProps({
  toolCall: {
    type: Object,
    required: true
  }
})

// 状态文本
const statusText = computed(() => {
  switch (props.toolCall.status) {
    case 'running': return '执行中'
    case 'completed': return '已完成'
    case 'error': return '失败'
    default: return '未知'
  }
})

// 格式化参数
const formatArgs = (args) => {
  try {
    if (typeof args === 'string') {
      // 尝试解析 JSON
      const parsed = JSON.parse(args)
      return JSON.stringify(parsed, null, 2)
    }
    return JSON.stringify(args, null, 2)
  } catch {
    return args
  }
}

// 格式化结果
const formatResult = (result) => {
  try {
    if (typeof result === 'string') {
      // 尝试解析 JSON
      const parsed = JSON.parse(result)
      return JSON.stringify(parsed, null, 2)
    }
    return JSON.stringify(result, null, 2)
  } catch {
    return result
  }
}
</script>

<style scoped>
.tool-call-card {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  font-size: 0.875rem;
}

.tool-call-card.status-running {
  border-color: var(--warning-color);
  background: #fffbeb;
}

.tool-call-card.status-completed {
  border-color: var(--success-color);
  background: #f0fdf4;
}

.tool-call-card.status-error {
  border-color: var(--error-color);
  background: #fef2f2;
}

/* 头部 */
.card-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-md);
}

.tool-icon {
  font-size: 1rem;
}

.tool-name {
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
}

.tool-status {
  font-size: 0.75rem;
  color: var(--text-secondary);
  padding: 2px 8px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-sm);
}

/* 内容区块 */
.card-section {
  margin-top: var(--spacing-md);
}

.section-title {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: var(--spacing-xs);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.section-content {
  background: var(--bg-tertiary);
  padding: var(--spacing-sm);
  border-radius: var(--radius-sm);
  font-family: 'Courier New', monospace;
  font-size: 0.75rem;
  line-height: 1.5;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
  max-height: 200px;
  overflow-y: auto;
}
</style>
