<script setup>
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppNav from '@/components/AppNav.vue'
import AppSidebar from '@/components/AppSidebar.vue'
import { auth } from '@/auth'

const route = useRoute()
const menuOpen = ref(false) // 좁은 화면에서 왼쪽 메뉴가 펼쳐져 있는지
watch(() => route.path, () => (menuOpen.value = false)) // 메뉴를 고르면 접는다
</script>

<template>
  <!-- 로그인 후: 위쪽 헤더(로고·사용자) + 왼쪽 메뉴 + 오른쪽 내용 -->
  <div v-if="auth.user && !route.meta.public" class="app-shell">
    <AppNav @toggle-menu="menuOpen = !menuOpen" />
    <div class="app-body">
      <AppSidebar :class="{ open: menuOpen }" />
      <main class="app-main">
        <!-- 첫 로그인 안내는 로그인 직후 비밀번호 변경 화면에서만 보여준다 (LoginView → PasswordView).
             [나중에]로 넘어간 뒤에는 다른 화면에 노란 안내 띠를 띄우지 않는다 (2026-10-27 결정) -->
        <RouterView />
      </main>
    </div>
  </div>
  <!-- 로그인 화면 등: 틀 없이 화면만 -->
  <RouterView v-else />
</template>
