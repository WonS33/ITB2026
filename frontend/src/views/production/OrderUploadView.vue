<script setup>
// 수주서 PDF 업로드 — 생산팀 수정 권한자만 (라우터에서 막고, 백엔드 API에서도 다시 확인함)
import { ref } from 'vue'
import FileUpload from '@/components/FileUpload.vue'

const saved = ref(false)
</script>

<template>
  <div>
    <FileUpload
      kind="sales_order_pdf"
      title="수주서 PDF 업로드"
      accept=".pdf"
      help="수주서 PDF(1쪽 = 1건)를 올리면 제품 1개를 1행으로 보여줍니다. PDF에서 잘린 값(…)은 빨간색으로 표시되니 전체 값으로 고친 뒤 저장하세요. 이미 저장된 판매번호는 건너뜁니다."
      @saved="saved = true"
    />
    <p v-if="saved" class="small">
      저장한 내용은 <RouterLink to="/production">대시보드</RouterLink>(판매 실적)와
      <RouterLink to="/production/serials">일련번호 조회</RouterLink>(플랜지 보완)에서 확인할 수 있습니다.
    </p>
  </div>
</template>
