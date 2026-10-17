<script setup>
import { canEdit } from '@/auth'
</script>

<template>
  <div>
    <h1 class="h4 mb-3">생산팀</h1>
    <p class="text-muted">생산 실적·일련번호 조회·납기 캘린더는 Phase 3부터 추가합니다.</p>
    <p>
      내 권한:
      <span v-if="canEdit('production')" class="badge bg-primary">열람·수정</span>
      <span v-else class="badge bg-secondary">열람만</span>
    </p>
  </div>
</template>
