import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  base: process.env.VITE_BASE || "/",
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    port: 3000,
    proxy: {
      '/analyze-homework-stream': {
        target: 'http://localhost:8000',
        timeout: 300000,       // 5 min — SSE 长连接需要充足超时
      },
      '/analyze-homework': {
        target: 'http://localhost:8000',
        timeout: 300000,
      },
      '/prepare-upload': {
        target: 'http://localhost:8000',
        timeout: 120000,
      },
      '/large-pdf': {
        target: 'http://localhost:8000',
        timeout: 120000,
      },
      '/grade-question': 'http://localhost:8000',
      '/review-question': 'http://localhost:8000',
      '/explain-question': 'http://localhost:8000',
      '/chat-question': 'http://localhost:8000',
      '/translate-question': 'http://localhost:8000',
      '/questions': 'http://localhost:8000',
      '/practice-orchestrator': {
        target: 'http://localhost:8000',
        timeout: 120000,
      },
      '/feedback': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
})
