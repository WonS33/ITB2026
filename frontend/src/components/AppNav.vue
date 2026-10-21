<script setup>
import { useRouter } from 'vue-router'
import { auth, homePath, logout, menuTeams, TEAM_LABELS, TEAM_ROUTES } from '@/auth'

const router = useRouter()

async function onLogout() {
  await logout()
  router.push('/login')
}
</script>

<template>
  <nav class="navbar navbar-expand navbar-light app-nav mb-4">
    <div class="container">
      <!-- 기업명: 누르면 내 첫 화면으로 -->
      <RouterLink class="navbar-brand d-flex align-items-center gap-2" :to="homePath()">
        <span class="brand-mark" aria-hidden="true"></span>
        <span class="brand-name">뉴토크코리아</span>
        <span class="brand-sub d-none d-lg-inline">경영지표 대시보드</span>
      </RouterLink>
      <!-- 열람 권한이 있는 팀 화면만 메뉴에 보인다 -->
      <ul class="navbar-nav me-auto">
        <li v-for="team in menuTeams()" :key="team" class="nav-item">
          <RouterLink class="nav-link" active-class="active" :to="TEAM_ROUTES[team]">
            {{ TEAM_LABELS[team] }}
          </RouterLink>
        </li>
        <li v-if="auth.user.has_full_access" class="nav-item">
          <RouterLink class="nav-link" active-class="active" to="/admin">관리자 설정</RouterLink>
        </li>
      </ul>
      <span class="navbar-text small me-3 d-none d-md-inline">
        <strong class="text-dark">{{ auth.user.name }}</strong> · {{ auth.user.role_display }}
      </span>
      <RouterLink class="btn btn-light btn-sm me-2" to="/password">비밀번호 변경</RouterLink>
      <button class="btn btn-light btn-sm" @click="onLogout">로그아웃</button>
    </div>
  </nav>
</template>

<style scoped>
.app-nav {
  background: #fff;
  border-bottom: 1px solid var(--line);
  padding-top: 0.6rem;
  padding-bottom: 0.6rem;
}
.brand-mark {
  width: 10px;
  height: 22px;
  border-radius: 3px;
  background: var(--brand);
}
.brand-name {
  font-weight: 800;
  color: var(--ink);
}
.brand-sub {
  font-size: 0.85rem;
  color: var(--muted);
  padding-left: 0.5rem;
  border-left: 1px solid var(--line);
}
.app-nav .nav-link {
  color: var(--muted);
  font-weight: 600;
  border-bottom: 2px solid transparent;
}
.app-nav .nav-link:hover {
  color: var(--ink);
}
/* 지금 보고 있는 팀 화면: 포인트 컬러 밑줄 */
.app-nav .nav-link.active {
  color: var(--brand-text);
  border-bottom-color: var(--brand);
}
</style>
