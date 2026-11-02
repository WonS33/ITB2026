<script setup>
// 왼쪽 메뉴: 볼 수 있는 팀 → 지금 보고 있는 팀은 하위 메뉴까지 펼쳐 보인다. 그 아래 '단가' 구역, 맨 아래 관리자 설정.
// (메뉴 숨김은 화면 편의일 뿐, 실제 권한 확인은 라우터와 백엔드 API에서 한다)
import { useRoute } from 'vue-router'
import { auth, canEdit, canView, menuTeams, TEAM_LABELS, TEAM_ROUTES } from '@/auth'
import { PRICE_MENU, TEAM_MENUS } from '@/menus'

const route = useRoute()

// 단가 구역 화면(meta.section)은 주소가 /service 아래여도 서비스팀 메뉴가 아니라 단가 구역을 강조한다
const isCurrentTeam = (team) => route.meta.team === team && !route.meta.section
const inPrices = () => route.meta.section === 'prices'
const priceItems = () => PRICE_MENU.filter((i) => !i.edit || canEdit('service'))
// 탭은 주소 뒤 ?view= 로 구분 (RouterLink의 강조 표시는 ?view=를 보지 않아 직접 비교)
const isPriceActive = (i) => route.path === i.path && (route.query.view ?? '') === i.view
const priceLink = (i) => ({ path: i.path, query: i.view ? { view: i.view } : {} })
const groupsOf = (team) => (TEAM_MENUS[team] ?? []).filter((g) => !g.edit || canEdit(team))

// 팀 아이콘 (선 아이콘, 글자색을 따라감)
const ICONS = {
  management: 'M4 20V10 M10 20V4 M16 20v-7 M3 20h18',
  production: 'M3 21V10l5 3V10l5 3V6l8-3v18H3Z M7 17h2 M12 17h2 M17 17h2',
  service: 'M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.5-.5-.5-2.5 2.5-2.5Z',
  lock: 'M6 11h12v10H6Z M8.5 11V7.5a3.5 3.5 0 0 1 7 0V11',
  pricing: 'M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8Z M7.5 7.5h.01',
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

    <!-- 단가 구역: 부품 단가(서비스팀 열람 권한자) + 제품 단가·원가(대표·관리자·경영지원팀) -->
    <nav v-if="canView('service') || auth.user.has_full_access" class="side-section" aria-label="단가">
      <div class="side-section-title">단가</div>
      <template v-if="canView('service')">
        <RouterLink to="/service/part-prices" class="side-item" :class="{ current: inPrices() }">
          <svg viewBox="0 0 24 24" class="side-icon" aria-hidden="true"><path :d="ICONS.pricing" /></svg>
          <span>부품 단가</span>
        </RouterLink>
        <div v-if="inPrices()" class="side-sub">
          <RouterLink v-for="i in priceItems()" :key="i.label" :to="priceLink(i)" class="side-subitem"
                      :class="{ active: isPriceActive(i) }">
            {{ i.label }}
          </RouterLink>
        </div>
      </template>
      <!-- 원가·마진·커미션은 대외비라 대표·관리자·경영지원팀에게만 보인다 (API에서도 확인) -->
      <RouterLink v-if="auth.user.has_full_access" to="/pricing" class="side-item" active-class="current">
        <svg viewBox="0 0 24 24" class="side-icon" aria-hidden="true"><path :d="ICONS.lock" /></svg>
        <span>제품 단가·원가</span>
        <span class="secret">대외비</span>
      </RouterLink>
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
.side-section {
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--line);
}
.side-section-title {
  padding: 0 0.75rem 0.35rem;
  color: var(--muted);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.02em;
}
/* 대외비 표시: 글자로 알려 준다 (색만으로 구분하지 않게) */
.secret {
  margin-left: auto;
  padding: 0.05rem 0.4rem;
  border: 1px solid currentColor;
  border-radius: 999px;
  font-size: 0.68rem;
  font-weight: 600;
  opacity: 0.8;
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
