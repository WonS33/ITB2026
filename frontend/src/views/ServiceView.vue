<script setup>
import { canEdit } from '@/auth'
</script>

<template>
  <div>
    <h1 class="h4 mb-3">서비스팀</h1>
    <p class="text-muted">출장보고서 업로드·집계·지도는 Phase 8부터 추가합니다.</p>
    <p>
      내 권한:
      <span v-if="canEdit('service')" class="badge bg-primary">열람·수정</span>
      <span v-else class="badge bg-secondary">열람만</span>
    </p>
  </div>
</template>
