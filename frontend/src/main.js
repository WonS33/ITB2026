import 'bootstrap/dist/css/bootstrap.min.css'
import './assets/theme.css' // 포인트 컬러·카드 스타일 (Bootstrap 다음에 불러와 덮어씀)
import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

const app = createApp(App)

app.use(router)

app.mount('#app')
