<script setup>
// 판매 실적: 산업 분야별(비중 도넛 + 순위 막대), 거래처별·제품별(순위 막대)
import { computed } from 'vue'
import RankingBar from '@/components/RankingBar.vue'
import ShareDoughnut from '@/components/ShareDoughnut.vue'
import { industryColor } from '@/charts'

const props = defineProps({
  sales: { type: Object, required: true }, // 대시보드 API의 sales
  label: { type: String, required: true }, // 예: 2026년 4분기
})

// 산업 분야 순위 막대도 도넛과 같은 고정 색을 쓴다
const industries = computed(() => props.sales.by_industry.map((i) => ({ ...i, color: industryColor(i.name) })))
</script>

<template>
  <div class="mb-4">
    <h2 class="h6 mb-1">{{ label }} 판매 실적 <span class="text-muted fw-normal">· 총 {{ sales.total.toLocaleString() }}대</span></h2>
    <p class="text-muted small mb-3">수주서 기준 (집계 날짜: 수주서 납기일, 거래처: 수주서 판매처 — 기업 확인 전 임시 기준)</p>
    <div class="row g-3">
      <div class="col-lg-6">
        <div class="card h-100"><div class="card-body">
          <h3 class="h6">산업 분야별 비중</h3>
          <ShareDoughnut :items="sales.by_industry" :total="sales.total" :color-of="industryColor" name-header="분야" />
        </div></div>
      </div>
      <div class="col-lg-6">
        <div class="card h-100"><div class="card-body">
          <h3 class="h6">산업 분야별 판매량 순위</h3>
          <RankingBar :items="industries" :total="sales.total" />
        </div></div>
      </div>
      <div class="col-lg-6">
        <div class="card h-100"><div class="card-body">
          <h3 class="h6">거래처별 판매량 순위</h3>
          <RankingBar :items="sales.by_customer" :total="sales.total" />
        </div></div>
      </div>
      <div class="col-lg-6">
        <div class="card h-100"><div class="card-body">
          <h3 class="h6">제품별 판매량 순위</h3>
          <RankingBar :items="sales.by_product" :total="sales.total" />
        </div></div>
      </div>
    </div>
  </div>
</template>
