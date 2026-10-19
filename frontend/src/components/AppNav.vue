<script setup>
import { useRouter } from 'vue-router'
import { auth, logout, TEAM_LABELS, TEAM_ROUTES } from '@/auth'

const router = useRouter()

async function onLogout() {
  await logout()
  router.push('/login')
}
</script>

<template>
  <nav class="navbar navbar-expand navbar-dark bg-dark mb-4">
    <div class="container">
      <span class="navbar-brand">경영지표 대시보드</span>
      <!-- 열람 권한이 있는 팀 화면만 메뉴에 보인다 -->
      <ul class="navbar-nav me-auto">
        <li v-for="team in auth.user.view_teams" :key="team" class="nav-item">
          <RouterLink class="nav-link" active-class="active" :to="TEAM_ROUTES[team]">
            {{ TEAM_LABELS[team] }}
          </RouterLink>
        </li>
      </ul>
      <span class="navbar-text me-3">{{ auth.user.name }} ({{ auth.user.role_display }})</span>
      <RouterLink class="btn btn-outline-light btn-sm me-2" to="/password">비밀번호 변경</RouterLink>
      <button class="btn btn-outline-light btn-sm" @click="onLogout">로그아웃</button>
    </div>
  </nav>
</template>
