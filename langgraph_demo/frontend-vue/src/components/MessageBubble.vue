<template>
  <div class="message" :class="message.role">
    <!-- 头像 -->
    <div class="message-avatar">
      {{ message.role === 'user' ? '👤' : '🤖' }}
    </div>
    
    <!-- 消息内容 -->
    <div class="message-content" :class="message.role">
      <!-- 文本内容 -->
      <div v-if="message.content" class="text-content">
        {{ message.content }}
      </div>
      
      <!-- 工具调用 -->
      <div v-if="message.toolCalls && message.toolCalls.length > 0" class="tool-calls">
        <div
          v-for="(tool, index) in message.toolCalls"
          :key="index"
          class="tool-item"
          :class="tool.type"
        >
          <span class="tool-icon">{{ tool.type === 'call' ? '🔧' : '✅' }}</span>
          <span class="tool-text">{{ tool.content }}</span>
        </div>
      </div>
      
      <!-- 空内容提示 -->
      <div v-if="!message.content && (!message.toolCalls || message.toolCalls.length === 0)" class="empty">
        <div class="typing-indicator">
          <span></span>
          <span></span>
          <span></span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  message: {
    type: Object,
    required: true
  }
})
</script>

<style scoped>
.message {
  margin-bottom: 16px;
  display: flex;
  gap: 12px;
  animation: fadeIn 0.3s ease-in;
}

.message.user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}

.message.user .message-avatar {
  background: #667eea;
}

.message.assistant .message-avatar {
  background: #10b981;
}

.message-content {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.6;
}

.message.user .message-content {
  background: #667eea;
  color: white;
  border-top-right-radius: 4px;
}

.message.assistant .message-content {
  background: white;
  color: #333;
  border-top-left-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.text-content {
  white-space: pre-wrap;
  word-break: break-word;
}

/* 工具调用样式 */
.tool-calls {
  margin-top: 8px;
}

.tool-item {
  padding: 8px 12px;
  border-radius: 4px;
  margin: 6px 0;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.tool-item.call {
  background: #fef3c7;
  border-left: 3px solid #f59e0b;
  color: #92400e;
}

.tool-item.result {
  background: #d1fae5;
  border-left: 3px solid #10b981;
  color: #065f46;
}

.tool-icon {
  font-size: 14px;
}

.tool-text {
  flex: 1;
}

/* 空内容（打字指示器） */
.empty {
  padding: 4px 0;
}

.typing-indicator {
  display: inline-flex;
  gap: 4px;
}

.typing-indicator span {
  width: 6px;
  height: 6px;
  background: #999;
  border-radius: 50%;
  animation: typing 1.4s infinite;
}

.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes typing {
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-8px); }
}
</style>
