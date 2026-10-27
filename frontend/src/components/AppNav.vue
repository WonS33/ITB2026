<script setup>
// 위쪽 헤더: 회사 로고 + 서비스 이름 / 오른쪽에 사용자 이름 (누르면 비밀번호 변경·로그아웃)
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { auth, homePath, logout } from '@/auth'
import logoMark from '@/assets/logo-mark.png'
import logoWordmark from '@/assets/logo-wordmark.png'

defineEmits(['toggle-menu'])

const router = useRouter()
const userMenu = ref(null)
const open = ref(false)

// 사용자 메뉴 바깥을 누르면 닫는다
function onClickOutside(e) {
  if (userMenu.value && !userMenu.value.contains(e.target)) open.value = false
}
onMounted(() => document.addEventListener('click', onClickOutside))
onBeforeUnmount(() => document.removeEventListener('click', onClickOutside))

async function onLogout() {
  open.value = false
  await logout()
  router.push('/login')
}
</script>

<template>
  <header class="app-header">
    <!-- 좁은 화면: 왼쪽 메뉴 여닫기 -->
    <button type="button" class="btn btn-light btn-sm d-md-none me-2" aria-label="메뉴 열기" @click="$emit('toggle-menu')">☰</button>

    <RouterLink class="brand" :to="homePath()" aria-label="뉴토크코리아 경영지표 대시보드 첫 화면">
      <img :src="logoMark" alt="" class="brand-mark" />
      <img :src="logoWordmark" alt="NEWTORK" class="brand-word" />
      <span class="brand-sub d-none d-sm-inline">경영지표 대시보드</span>
    </RouterLink>

    <div ref="userMenu" class="ms-auto position-relative">
      <button type="button" class="user-chip" :aria-expanded="open" @click="open = !open">
        <span class="avatar">{{ auth.user.name?.[0] ?? '?' }}</span>
        <span class="text-start lh-sm d-none d-sm-block">
          <span class="d-block fw-semibold">{{ auth.user.name }}</span>
          <span class="d-block small text-muted">{{ auth.user.role_display }}</span>
        </span>
        <span class="caret" aria-hidden="true">▾</span>
      </button>
      <div v-if="open" class="user-menu">
        <RouterLink class="user-menu-item" to="/password" @click="open = false">비밀번호 변경</RouterLink>
        <button type="button" class="user-menu-item" @click="onLogout">로그아웃</button>
      </div>
    </div>
  </header>
</template>

<style scoped>
.app-header {
  position: sticky;
  top: 0;
  z-index: 1030;
  display: flex;
  align-items: center;
  height: var(--header-h);
  padding: 0 1.25rem;
  background: #fff;
  border-bottom: 1px solid var(--line);
}
.brand {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  text-decoration: none;
}
.brand-mark {
  height: 30px;
}
.brand-word {
  height: 17px;
}
.brand-sub {
  margin-left: 0.4rem;
  padding-left: 0.8rem;
  border-left: 1px solid var(--line);
  color: var(--muted);
  font-size: 0.95rem;
}
.user-chip {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.3rem 0.75rem 0.3rem 0.35rem;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 999px;
  color: var(--ink);
  font-size: 0.875rem;
}
.user-chip:hover {
  background: var(--surface-2);
}
.avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--surface-2);
  color: var(--navy);
  font-weight: 700;
}
.caret {
  color: var(--muted);
  font-size: 0.75rem;
}
.user-menu {
  position: absolute;
  right: 0;
  top: calc(100% + 6px);
  min-width: 160px;
  padding: 0.35rem;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(16, 24, 40, 0.1);
}
.user-menu-item {
  display: block;
  width: 100%;
  padding: 0.5rem 0.75rem;
  border: 0;
  border-radius: 8px;
  background: none;
  color: var(--ink);
  text-align: left;
  text-decoration: none;
  font-size: 0.9rem;
}
.user-menu-item:hover {
  background: var(--surface-2);
  color: var(--ink);
}
</style>
