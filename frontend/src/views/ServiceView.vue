<script setup>
import PeriodSelector from '@/components/PeriodSelector.vue'
import { canEdit } from '@/auth'
import { periodLabel } from '@/period'
</script>

<template>
  <div>
    <div class="d-flex align-items-center gap-2 mb-3">
      <h1 class="h4 mb-0">서비스팀</h1>
      <span v-if="canEdit('service')" class="badge bg-primary">열람·수정</span>
      <span v-else class="badge bg-secondary">열람만</span>
    </div>
    <PeriodSelector />
    <p class="text-muted">{{ periodLabel() }} 기준 출장보고서 집계·지도는 Phase 8부터 추가합니다.</p>
  </div>
</template>
