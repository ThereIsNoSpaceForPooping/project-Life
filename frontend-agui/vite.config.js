// -*- coding: utf-8 -*-
/**
 * Vite 配置文件
 * 
 * 配置开发服务器代理，解决跨域问题
 */

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  // 使用 Vue 插件
  plugins: [vue()],
  
  // 开发服务器配置
  server: {
    port: 3000,           // 前端端口
    open: true,           // 自动打开浏览器
    
    // 代理配置：将 /api 请求转发到后端
    proxy: {
      '/api': {
        target: 'http://localhost:8005',  // LangGraph Advanced 地址
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  },
  
  // 路径别名
  resolve: {
    alias: {
      '@': '/src'
    }
  }
})
