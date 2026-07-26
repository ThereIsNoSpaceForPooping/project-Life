import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      // API 代理配置
      '/api': {
        target: 'http://localhost:8004',
        changeOrigin: true,
        // SSE 流式响应需要关闭超时
        timeout: 0,
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq) => {
            // 禁用代理缓冲，确保 SSE 实时传递
            proxyReq.removeHeader('accept-encoding')
          })
        },
      }
    }
  }
})
