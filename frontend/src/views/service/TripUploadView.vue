<script setup>
// 출장보고서 PDF 업로드 — 서비스팀 수정 권한자만 (라우터에서 막고, 백엔드 API에서도 다시 확인함)
import { ref } from 'vue'
import FileUpload from '@/components/FileUpload.vue'

const saved = ref(false)
</script>

<template>
  <div>
    <FileUpload
      kind="trip_report_pdf"
      title="출장보고서 PDF 업로드"
      accept=".pdf"
      help="출장보고서 PDF(1쪽 = 1건)를 올리면 보고서 1건을 1행으로 보여줍니다. 시·도·시·군은 처음 보는 요청처일 때 직접 고르면 다음부터 자동으로 채워집니다. 잘린 부품명·요청처(…)는 전체 이름으로 고친 뒤 저장하세요."
      @saved="saved = true"
    />
    <p v-if="saved" class="small">
      저장한 내용은 <RouterLink to="/service">대시보드</RouterLink>와
      <RouterLink to="/service/reports">출장보고서 목록</RouterLink>에서 확인할 수 있습니다.
      새 부품이 나왔다면 <RouterLink to="/service/part-prices/input">부품 단가 입력</RouterLink>에서 단가를 넣어 주세요.
    </p>
  </div>
</template>
