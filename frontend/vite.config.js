import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  // /api 로 시작하는 요청은 Django 개발 서버로 넘긴다.
  // 화면과 API가 같은 주소(localhost:5173)처럼 보이므로 세션 쿠키를 그대로 쓸 수 있고 CORS 설정이 필요 없다.
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
