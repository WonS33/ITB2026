<script setup>
import FileUpload from '@/components/FileUpload.vue'
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
    <p class="text-muted">{{ periodLabel() }} 기준 출장 집계·지도는 Phase 9부터 추가합니다.</p>

    <!-- 업로드는 서비스팀 수정 권한자에게만 보인다 (백엔드 API에서도 권한을 다시 확인함) -->
    <FileUpload
      v-if="canEdit('service')"
      kind="trip_report_pdf"
      title="출장보고서 PDF 업로드"
      accept=".pdf"
      help="출장보고서 PDF(1쪽 = 1건)를 올리면 보고서 1건을 1행으로 보여줍니다. 시·도는 처음 보는 요청처일 때 직접 고르면 다음부터 자동으로 채워집니다. 잘린 부품명·요청처(…)는 전체 이름으로 고친 뒤 저장하세요."
    />
  </div>
</template>
