<!--
  Agent 状态组件
  
  显示当前 Agent 的执行状态
-->

<template>
  <div class="agent-status">
    <div class="status-header">
      <h3>Agent 状态</h3>
      <div class="status-indicator" :class="{ running: status.isRunning }">
        <span class="indicator-dot"></span>
        <span class="indicator-text">{{ status.isRunning ? '运行中' : '空闲' }}</span>
      </div>
    </div>
    
    <div class="status-content">
      <!-- 当前步骤 -->
      <div v-if="status.currentStep" class="status-item">
        <div class="item-label">当前步骤</div>
        <div class="item-value">{{ status.currentStep }}</div>
      </div>
      
      <!-- 进度条 -->
      <div v-if="status.isRunning" class="status-item">
        <div class="item-label">执行进度</div>
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: status.progress + '%' }"></div>
        </div>
        <div class="progress-text">{{ status.progress }}%</div>
      </div>
      
      <!-- 空闲状态 -->
      <div v-if="!status.isRunning && !status.currentStep" class="idle-state">
        <div class="idle-icon">💤</div>
        <div class="idle-text">等待任务</div>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * Agent 状态逻辑
 */

defineProps({
  status: {
    type: Object,
    default: () => ({
      currentStep: null,
      isRunning: false,
      progress: 0
    })
  }
})
</script>

<style scoped>
.agent-status {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  margin-bottom: var(--spacing-md);
}

/* 头部 */
.status-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-md);
}

.status-header h3 {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

/* 状态指示器 */
.status-indicator {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  background: var(--bg-tertiary);
  font-size: 0.75rem;
}

.status-indicator.running {
  background: #fef3c7;
  color: var(--warning-color);
}

.indicator-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-tertiary);
}

.status-indicator.running .indicator-dot {
  background: var(--warning-color);
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* 内容 */
.status-content {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.status-item {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.item-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.item-value {
  font-size: 0.875rem;
  color: var(--text-primary);
  padding: var(--spacing-sm);
  background: var(--bg-primary);
  border-radius: var(--radius-sm);
  word-break: break-word;
}

/* 进度条 */
.progress-bar {
  height: 8px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--primary-color);
  transition: width 0.3s ease;
}

.progress-text {
  font-size: 0.75rem;
  color: var(--text-secondary);
  text-align: right;
}

/* 空闲状态 */
.idle-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-lg);
  color: var(--text-tertiary);
}

.idle-icon {
  font-size: 2rem;
}

.idle-text {
  font-size: 0.875rem;
}
</style>
