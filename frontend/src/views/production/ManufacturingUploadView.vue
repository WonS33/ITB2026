<script setup>
// 제조내역 엑셀 업로드 — 생산팀 수정 권한자만 (라우터에서 막고, 백엔드 API에서도 다시 확인함)
import { ref } from 'vue'
import FileUpload from '@/components/FileUpload.vue'

const saved = ref(false)
</script>

<template>
  <div>
    <FileUpload
      kind="manufacturing_excel"
      title="제조내역 엑셀 업로드"
      accept=".xlsx"
      help="제조내역 엑셀(.xlsx)을 올리면 추출 결과를 먼저 보여줍니다. 확인·수정한 뒤 [저장]을 눌러야 반영됩니다. 이미 저장된 일련번호는 건너뜁니다."
      @saved="saved = true"
    />
    <p v-if="saved" class="small">
      저장한 내용은 <RouterLink to="/production">대시보드</RouterLink>(생산량),
      <RouterLink to="/production/serials">일련번호 조회</RouterLink>,
      <RouterLink to="/production/calendar">납기 캘린더</RouterLink>에서 확인할 수 있습니다.
    </p>
  </div>
</template>
