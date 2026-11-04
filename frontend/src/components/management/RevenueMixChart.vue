<script setup>
// 매출 구성(제품·상품·용역) 월별 누적 막대 (조원 저장소 revenue-mix-chart 를 옮김)
// 임시저장 달은 흐리게 + 아래 "미확정", 데이터 없는 달은 빈칸. [표로 보기]
import { computed, ref } from 'vue'
import { Bar } from 'vue-chartjs'
import { GRID_COLOR, SERIES_COLORS } from '@/charts'
import { won, wonShort } from '@/money'

const props = defineProps({ points: { type: Array, required: true } })
const showTable = ref(false)
const PARTS = [
  { key: 'product', label: '제품', color: SERIES_COLORS[0] },
  { key: 'merchandise', label: '상품', color: SERIES_COLORS[1] },
  { key: 'service', label: '용역', color: SERIES_COLORS[2] },
]
const STATUS = { confirmed: '확정', draft: '미확정', missing: '데이터 없음', pending: '마감 전' }
const isDraft = (p) => p.status === 'draft'

const data = computed(() => ({
  labels: props.points.map((p) => (isDraft(p) ? [`${p.month}월`, '미확정'] : `${p.month}월`)),
  datasets: PARTS.map((part) => ({
    label: part.label,
    data: props.points.map((p) => p[part.key]),
    backgroundColor: props.points.map((p) => (isDraft(p) ? `${part.color}59` : part.color)),
    borderColor: '#ffffff', // 쌓은 조각 사이 흰 틈
    borderWidth: { top: 2 },
    maxBarThickness: 32,
    stack: 'mix',
  })),
}))
const options = {
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  interaction: { mode: 'index', intersect: false },
  plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${ctx.raw === null ? '-' : won(ctx.raw)}` } } },
  scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, beginAtZero: true, grid: { color: GRID_COLOR }, ticks: { callback: (v) => wonShort(v) } } },
}
const total = (p) => (p.product === null ? null : p.product + p.merchandise + p.service)
</script>

<template>
  <div class="card h-100"><div class="card-body">
    <div class="d-flex flex-wrap align-items-center gap-3 mb-2">
      <h3 class="h6 mb-0">매출 구성 월별 추이 <small class="text-muted fw-normal">(최근 12개월)</small></h3>
      <span v-for="p in PARTS" :key="p.key" class="small"><span class="swatch" :style="{ background: p.color }"></span>{{ p.label }}</span>
      <button type="button" class="btn btn-sm btn-light ms-auto" @click="showTable = !showTable">{{ showTable ? '그래프로 보기' : '표로 보기' }}</button>
    </div>
    <div v-if="!showTable" style="height: 240px"><Bar :data="data" :options="options" /></div>
    <div v-else class="table-responsive">
      <table class="table table-sm small mb-0">
        <thead class="table-light"><tr><th>월</th><th>상태</th><th class="text-end">제품(원)</th><th class="text-end">상품(원)</th><th class="text-end">용역(원)</th><th class="text-end">합계(원)</th></tr></thead>
        <tbody>
          <tr v-for="p in points" :key="`${p.year}-${p.month}`">
            <td>{{ p.year }}-{{ String(p.month).padStart(2, '0') }}</td><td>{{ STATUS[p.status] }}</td>
            <td class="text-end">{{ p.product?.toLocaleString() ?? '-' }}</td>
            <td class="text-end">{{ p.merchandise?.toLocaleString() ?? '-' }}</td>
            <td class="text-end">{{ p.service?.toLocaleString() ?? '-' }}</td>
            <td class="text-end">{{ total(p)?.toLocaleString() ?? '-' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <p class="small text-muted mt-2 mb-0">흐린 막대 = 임시저장(확정 전, 참고용)</p>
  </div></div>
</template>

<style scoped>
.swatch { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; vertical-align: middle; }
</style>
