<script setup>
import { useRoute } from 'vue-router'
import AppNav from '@/components/AppNav.vue'
import { auth } from '@/auth'

const route = useRoute()
</script>

<template>
  <AppNav v-if="auth.user" />
  <main class="container">
    <!-- 첫 로그인 안내: 비밀번호를 바꿀 때까지 모든 화면 위쪽에 보여준다 -->
    <div
      v-if="auth.user?.must_change_password && route.path !== '/password'"
      class="alert alert-warning d-flex align-items-center justify-content-between py-2"
    >
      <span>초기 비밀번호를 사용 중입니다. 본인만 아는 비밀번호로 바꿔 주세요.</span>
      <RouterLink :to="{ path: '/password', query: { next: route.fullPath } }" class="btn btn-warning btn-sm">지금 변경</RouterLink>
    </div>
    <RouterView />
  </main>
</template>
