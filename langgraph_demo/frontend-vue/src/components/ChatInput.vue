<template>
  <div class="chat-input-container">
    <input
      type="text"
      class="chat-input"
      :value="modelValue"
      @input="$emit('update:modelValue', $event.target.value)"
      @keypress.enter="handleSend"
      :disabled="disabled"
      placeholder="输入消息..."
      autocomplete="off"
      ref="inputRef"
    />
    <button
      class="send-button"
      @click="handleSend"
      :disabled="disabled || !modelValue.trim()"
    >
      发送
    </button>
    <button class="clear-button" @click="$emit('clear')">
      清空对话
    </button>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  },
  disabled: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'send', 'clear'])

const inputRef = ref(null)

// 发送消息
const handleSend = () => {
  if (props.modelValue.trim() && !props.disabled) {
    emit('send')
  }
}

// 自动聚焦
onMounted(() => {
  inputRef.value?.focus()
})
</script>

<style scoped>
.chat-input-container {
  padding: 16px 20px;
  background: white;
  border-top: 1px solid #e5e7eb;
  display: flex;
  gap: 12px;
}

.chat-input {
  flex: 1;
  padding: 12px 16px;
  border: 2px solid #e5e7eb;
  border-radius: 24px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
}

.chat-input:focus {
  border-color: #667eea;
}

.chat-input:disabled {
  background: #f3f4f6;
  cursor: not-allowed;
}

.send-button {
  padding: 12px 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 24px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.send-button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.send-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.clear-button {
  padding: 8px 16px;
  background: #ef4444;
  color: white;
  border: none;
  border-radius: 16px;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.2s;
}

.clear-button:hover {
  background: #dc2626;
}
</style>
