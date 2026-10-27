<script setup>
// 팀 화면 틀: 페이지 제목(팀 · 지금 메뉴) + 오른쪽 기간 선택 자리 + 내용(하위 화면)
// 팀 메뉴는 왼쪽 메뉴(AppSidebar)에 있다.
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { canEdit, TEAM_LABELS } from '@/auth'
import { TEAM_MENUS } from '@/menus'

const route = useRoute()
const team = computed(() => route.meta.team)
const current = computed(() => (TEAM_MENUS[team.value] ?? []).flatMap((g) => g.items).find((i) => i.to === route.path))
</script>

<template>
  <div>
    <div class="page-head">
      <div>
        <div class="page-eyebrow">
          {{ TEAM_LABELS[team] }}
          <span v-if="canEdit(team)" class="badge badge-soft-brand ms-1">열람·수정</span>
          <span v-else class="badge badge-soft ms-1">열람만</span>
        </div>
        <h1 class="page-title">{{ current?.label ?? TEAM_LABELS[team] }}</h1>
      </div>
      <!-- 기간 선택(PeriodSelector)이 있는 화면은 여기로 옮겨져 제목 오른쪽에 보인다 -->
      <div id="page-actions" class="page-actions"></div>
    </div>
    <RouterView />
  </div>
</template>
