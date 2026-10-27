<script setup>
// 유상 A/S 견적서 PDF 업로드 → 부품 단가 — 서비스팀 수정 권한자만 (라우터에서 막고, 백엔드 API에서도 다시 확인함)
import { ref } from 'vue'
import FileUpload from '@/components/FileUpload.vue'

const saved = ref(false)
</script>

<template>
  <div>
    <FileUpload
      kind="quote_pdf"
      title="견적서 PDF 업로드 (부품 단가)"
      accept=".pdf"
      help="유상 A/S 견적서 PDF(1쪽 = 견적서 1건)를 올리면 품목 1줄을 1행으로 보여줍니다. 단가(부가세 제외)는 견적 날짜부터 적용됩니다. 견적서 품명마다 출장보고서에 쓰는 부품명을 고르면 다음부터 자동으로 채워집니다. 이미 저장된 견적 번호·품명은 건너뜁니다."
      @saved="saved = true"
    />
    <p v-if="saved" class="small">
      저장한 단가는 <RouterLink to="/service/part-prices">교체부품 단가</RouterLink>에서 출처(견적 번호)와 함께 확인할 수 있습니다.
    </p>
  </div>
</template>
