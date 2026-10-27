<script setup>
// 왼쪽 메뉴: 볼 수 있는 팀 → 지금 보고 있는 팀은 하위 메뉴까지 펼쳐 보인다. 맨 아래 관리자 설정.
// (메뉴 숨김은 화면 편의일 뿐, 실제 권한 확인은 라우터와 백엔드 API에서 한다)
import { useRoute } from 'vue-router'
import { auth, canEdit, menuTeams, TEAM_LABELS, TEAM_ROUTES } from '@/auth'
import { TEAM_MENUS } from '@/menus'

const route = useRoute()

const isCurrentTeam = (team) => route.meta.team === team
const groupsOf = (team) => (TEAM_MENUS[team] ?? []).filter((g) => !g.edit || canEdit(team))

// 팀 아이콘 (선 아이콘, 글자색을 따라감)
const ICONS = {
  production: 'M3 21V10l5 3V10l5 3V6l8-3v18H3Z M7 17h2 M12 17h2 M17 17h2',
  service: 'M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.5-.5-.5-2.5 2.5-2.5Z',
  admin: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z M19.4 13a7.5 7.5 0 0 0 0-2l2-1.5-2-3.5-2.4 1a7.5 7.5 0 0 0-1.7-1L15 3.5h-4l-.4 2.5a7.5 7.5 0 0 0-1.7 1l-2.4-1-2 3.5 2 1.5a7.5 7.5 0 0 0 0 2l-2 1.5 2 3.5 2.4-1a7.5 7.5 0 0 0 1.7 1l.4 2.5h4l.4-2.5a7.5 7.5 0 0 0 1.7-1l2.4 1 2-3.5-2-1.5Z',
}
</script>

<template>
  <aside class="app-sidebar" aria-label="메뉴">
    <nav>
      <template v-for="team in menuTeams()" :key="team">
        <RouterLink :to="TEAM_ROUTES[team]" class="side-item" :class="{ current: isCurrentTeam(team) }">
          <svg viewBox="0 0 24 24" class="side-icon" aria-hidden="true"><path :d="ICONS[team]" /></svg>
          <span>{{ TEAM_LABELS[team] }}</span>
          <span v-if="!canEdit(team)" class="view-only">열람만</span>
        </RouterLink>
        <!-- 지금 팀의 하위 메뉴 -->
        <div v-if="isCurrentTeam(team)" class="side-sub">
          <template v-for="g in groupsOf(team)" :key="g.group">
            <div class="side-group">{{ g.group }}</div>
            <!-- exact-active-class: 대시보드(/production)가 하위 주소에서 함께 강조되지 않게 정확히 같은 주소만 강조 -->
            <RouterLink v-for="item in g.items" :key="item.to" :to="item.to" class="side-subitem" exact-active-class="active">
              {{ item.label }}
            </RouterLink>
          </template>
        </div>
      </template>
    </nav>

    <nav v-if="auth.user.has_full_access" class="side-bottom">
      <RouterLink to="/admin" class="side-item" active-class="current">
        <svg viewBox="0 0 24 24" class="side-icon" aria-hidden="true"><path :d="ICONS.admin" /></svg>
        <span>관리자 설정</span>
      </RouterLink>
    </nav>
  </aside>
</template>

<style scoped>
.app-sidebar {
  position: sticky;
  top: var(--header-h);
  display: flex;
  flex-direction: column;
  flex: 0 0 var(--sidebar-w);
  width: var(--sidebar-w);
  height: calc(100vh - var(--header-h));
  overflow-y: auto;
  padding: 1rem 0.75rem;
  background: #fff;
  border-right: 1px solid var(--line);
}
.side-bottom {
  margin-top: auto;
  padding-top: 0.75rem;
  border-top: 1px solid var(--line);
}
.side-item {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.6rem 0.75rem;
  margin-bottom: 0.15rem;
  border-radius: 10px;
  color: var(--ink);
  font-weight: 600;
  text-decoration: none;
}
.side-item:hover {
  background: var(--surface-2);
  color: var(--ink);
}
/* 지금 보고 있는 팀: 짙은 남색 */
.side-item.current {
  background: var(--navy);
  color: #fff;
}
.side-icon {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.view-only {
  margin-left: auto;
  font-size: 0.7rem;
  font-weight: 500;
  opacity: 0.7;
}
.side-sub {
  margin: 0.25rem 0 0.75rem;
}
.side-group {
  padding: 0.6rem 0.75rem 0.25rem 2.6rem;
  color: var(--muted);
  font-size: 0.75rem;
  font-weight: 600;
}
.side-subitem {
  display: block;
  padding: 0.4rem 0.75rem 0.4rem 2.6rem;
  border-radius: 8px;
  color: var(--ink-2);
  font-size: 0.9rem;
  text-decoration: none;
}
.side-subitem:hover {
  background: var(--surface-2);
  color: var(--ink);
}
/* 지금 보고 있는 하위 메뉴: 포인트 컬러 */
.side-subitem.active {
  color: var(--brand-text);
  font-weight: 700;
  background: var(--brand-soft);
}

/* 좁은 화면: 평소엔 숨기고, 헤더의 ☰ 버튼으로 연다 */
@media (max-width: 767.98px) {
  .app-sidebar {
    position: fixed;
    left: 0;
    z-index: 1020;
    transform: translateX(-100%);
    transition: transform 0.2s;
    box-shadow: 0 8px 24px rgba(16, 24, 40, 0.12);
  }
  .app-sidebar.open {
    transform: none;
  }
}
</style>
