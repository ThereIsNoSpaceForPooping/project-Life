<!--
  根组件
  
  整合所有子组件，提供整体布局
-->

<template>
  <div class="app">
    <header class="app-header">
      <h1>AG-UI 前端</h1>
      <p class="subtitle">通过 LangGraph Advanced 调用 MCP 和 A2A</p>
    </header>
    
    <main class="app-main">
      <!-- 左侧：聊天区域 -->
      <div class="chat-section">
        <ChatWindow ref="chatWindow" />
      </div>
      
      <!-- 右侧：调试面板 -->
      <div class="debug-section">
        <AgentStatus :status="agentStatus" />
        <EventLog :events="eventLog" />
      </div>
    </main>
    
    <footer class="app-footer">
      <p>AG-UI Protocol Demo | LangGraph Advanced + MCP + A2A</p>
    </footer>
  </div>
</template>

<script setup>
/**
 * 根组件逻辑
 * 
 * 管理全局状态和组件通信
 */

import { ref, provide } from 'vue'
import ChatWindow from './components/ChatWindow.vue'
import AgentStatus from './components/AgentStatus.vue'
import EventLog from './components/EventLog.vue'
import { StateManager } from './core/state-manager.js'

// 全局状态管理器
const stateManager = new StateManager()

// Agent 状态
const agentStatus = ref({
  currentStep: null,
  isRunning: false,
  progress: 0
})

// 事件日志
const eventLog = ref([])

// 聊天窗口引用
const chatWindow = ref(null)

// 提供状态管理器给子组件
provide('stateManager', stateManager)

// 添加事件到日志
const addEvent = (event) => {
  eventLog.value.unshift({
    timestamp: new Date().toLocaleTimeString(),
    ...event
  })
  
  // 保持日志数量在 100 条以内
  if (eventLog.value.length > 100) {
    eventLog.value = eventLog.value.slice(0, 100)
  }
}

// 更新 Agent 状态
const updateAgentStatus = (status) => {
  agentStatus.value = { ...agentStatus.value, ...status }
}

// 提供给子组件使用
provide('addEvent', addEvent)
provide('updateAgentStatus', updateAgentStatus)
</script>

<style scoped>
/* 应用容器 */
.app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-primary);
}

/* 头部 */
.app-header {
  padding: 1rem 2rem;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
}

.app-header h1 {
  margin: 0;
  font-size: 1.5rem;
  color: var(--text-primary);
}

.subtitle {
  margin: 0.25rem 0 0 0;
  font-size: 0.875rem;
  color: var(--text-secondary);
}

/* 主内容区 */
.app-main {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* 聊天区域 */
.chat-section {
  flex: 2;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border-color);
}

/* 调试区域 */
.debug-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 底部 */
.app-footer {
  padding: 0.75rem 2rem;
  background: var(--bg-secondary);
  border-top: 1px solid var(--border-color);
  text-align: center;
}

.app-footer p {
  margin: 0;
  font-size: 0.75rem;
  color: var(--text-secondary);
}
</style>
