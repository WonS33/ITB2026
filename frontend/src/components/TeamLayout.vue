<script setup>
// 팀 화면 틀: 왼쪽 메뉴 + 오른쪽 내용(하위 화면). 좁은 화면에서는 [메뉴] 버튼으로 여닫는다.
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { canEdit, TEAM_LABELS } from '@/auth'
import { TEAM_MENUS } from '@/menus'

const route = useRoute()
const team = computed(() => route.meta.team)
const groups = computed(() => (TEAM_MENUS[team.value] ?? []).filter((g) => !g.edit || canEdit(team.value)))
const current = computed(() => groups.value.flatMap((g) => g.items).find((i) => i.to === route.path))

const open = ref(false) // 좁은 화면에서 메뉴가 펼쳐져 있는지
watch(() => route.path, () => (open.value = false)) // 메뉴를 고르면 접는다
</script>

<template>
  <div class="row g-4">
    <aside class="col-md-3 col-lg-2">
      <div class="d-flex align-items-center gap-2 mb-2">
        <h1 class="h5 mb-0">{{ TEAM_LABELS[team] }}</h1>
        <span v-if="canEdit(team)" class="badge bg-primary">열람·수정</span>
        <span v-else class="badge bg-secondary">열람만</span>
      </div>
      <button
        type="button"
        class="btn btn-outline-secondary btn-sm w-100 d-md-none mb-2 text-start"
        :aria-expanded="open"
        @click="open = !open"
      >
        ☰ 메뉴 · {{ current?.label }}
      </button>
      <nav class="side-menu" :class="{ 'd-none': !open }" aria-label="팀 메뉴">
        <template v-for="g in groups" :key="g.group">
          <div class="text-muted small fw-semibold mt-3 mb-1 px-2">{{ g.group }}</div>
          <!-- exact-active-class: 대시보드(/production)가 하위 주소에서 함께 강조되지 않게 정확히 같은 주소만 강조 -->
          <RouterLink
            v-for="item in g.items"
            :key="item.to"
            :to="item.to"
            class="nav-link rounded px-2 py-1"
            exact-active-class="active"
          >
            {{ item.label }}
          </RouterLink>
        </template>
      </nav>
    </aside>
    <section class="col-md-9 col-lg-10">
      <RouterView />
    </section>
  </div>
</template>

<style scoped>
.side-menu .nav-link {
  color: var(--bs-body-color, #212529);
}
.side-menu .nav-link:hover {
  background: #f1f3f5;
}
.side-menu .nav-link.active {
  background: #0d6efd;
  color: #fff;
}
/* 넓은 화면에서는 [메뉴] 버튼 없이 항상 펼쳐 둔다 */
@media (min-width: 768px) {
  .side-menu.d-none {
    display: block !important;
  }
}
</style>
