<template>
  <div class="chat-container">
    <!-- 头部 -->
    <div class="chat-header">
      <h1>🤖 LangGraph Agent Demo</h1>
      <p>支持工具调用和对话记忆</p>
    </div>

    <!-- 消息列表 -->
    <div class="chat-messages" ref="messagesContainer">
      <MessageBubble
        v-for="(msg, index) in messages"
        :key="index"
        :message="msg"
      />
      
      <!-- 打字指示器 -->
      <div v-if="isLoading" class="message assistant">
        <div class="message-avatar">🤖</div>
        <div class="message-content">
          <div class="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>
      </div>
    </div>

    <!-- 输入区域 -->
    <ChatInput
      v-model="inputMessage"
      :disabled="isLoading"
      @send="sendMessage"
      @clear="clearChat"
    />
  </div>
</template>

<script setup>
import { ref, nextTick, watch } from 'vue'
import MessageBubble from './MessageBubble.vue'
import ChatInput from './ChatInput.vue'
import { chatStream } from '../api/chat'

// 消息列表
const messages = ref([
  {
    role: 'assistant',
    content: '你好！我是 LangGraph 智能体，可以帮你查询天气、计算数学表达式、搜索知识库。试试问我："北京今天天气怎么样？"'
  }
])

// 输入消息
const inputMessage = ref('')

// 加载状态
const isLoading = ref(false)

// 消息容器引用
const messagesContainer = ref(null)

// 对话 ID（用于记忆）
const conversationId = ref('conv-' + Date.now())

// 滚动到底部
const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

// 监听消息变化，自动滚动
watch(messages, scrollToBottom, { deep: true })

// 发送消息
const sendMessage = async () => {
  const message = inputMessage.value.trim()
  if (!message || isLoading.value) return

  // 添加用户消息
  messages.value.push({
    role: 'user',
    content: message
  })

  // 清空输入
  inputMessage.value = ''
  isLoading.value = true

  // 添加助手消息占位
  const assistantIndex = messages.value.length
  messages.value.push({
    role: 'assistant',
    content: '',
    toolCalls: []
  })

  try {
    // 调用流式 API
    await chatStream(
      [{ role: 'user', content: message }],
      conversationId.value,
      (chunk) => {
        const assistantMsg = messages.value[assistantIndex]
        
        switch (chunk.type) {
          case 'content':
            assistantMsg.content += chunk.content
            break
          case 'tool_call':
            assistantMsg.toolCalls.push({
              type: 'call',
              content: chunk.content
            })
            break
          case 'tool_result':
            assistantMsg.toolCalls.push({
              type: 'result',
              content: chunk.content
            })
            break
          case 'error':
            assistantMsg.content = `❌ 错误: ${chunk.content}`
            break
        }
      }
    )
  } catch (error) {
    messages.value[assistantIndex].content = `❌ 请求失败: ${error.message}`
  } finally {
    isLoading.value = false
  }
}

// 清空对话
const clearChat = () => {
  messages.value = [
    {
      role: 'assistant',
      content: '对话已清空。有什么可以帮你的？'
    }
  ]
  // 生成新的对话 ID
  conversationId.value = 'conv-' + Date.now()
}
</script>

<style scoped>
.chat-container {
  width: 100%;
  max-width: 800px;
  height: 90vh;
  background: white;
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 20px;
  text-align: center;
}

.chat-header h1 {
  font-size: 20px;
  font-weight: 600;
}

.chat-header p {
  font-size: 12px;
  opacity: 0.9;
  margin-top: 4px;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: #f8f9fa;
}

.message {
  margin-bottom: 16px;
  display: flex;
  gap: 12px;
  animation: fadeIn 0.3s ease-in;
}

.message.assistant {
  flex-direction: row;
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
  background: #10b981;
}

.message-content {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.6;
  background: white;
  color: #333;
  border-top-left-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* 打字指示器 */
.typing-indicator {
  display: inline-flex;
  gap: 4px;
  padding: 4px 0;
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

@keyframes typing {
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-8px); }
}
</style>
