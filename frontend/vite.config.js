import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    // 本機開發：前端在 http://localhost:5173，/api 轉給 scripts/dev_server.py（port 8000）
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
