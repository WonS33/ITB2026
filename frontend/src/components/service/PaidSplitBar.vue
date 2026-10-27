<script setup>
// 순위 가로 막대를 유상·무상으로 나눠 쌓은 그래프 (예: A/S 제품 모델별 대수)
// 무상(보증) A/S가 많은 항목이 품질 문제 신호일 수 있어, 많고 적음과 함께 무상 비중을 보여준다
import { computed } from 'vue'
import { Bar } from 'vue-chartjs'
import { GRID_COLOR, paidColor, percent } from '@/charts'

const props = defineProps({
  items: { type: Array, required: true }, // [{ name, quantity, paid, unpaid }] (많은 순서)
  unit: { type: String, default: '대' },
  limit: { type: Number, default: 10 },
})

const shown = computed(() => props.items.slice(0, props.limit))
const END_RADIUS = { topRight: 4, bottomRight: 4 } // 가로 막대는 오른쪽 끝만 둥글게

const chartData = computed(() => ({
  labels: shown.value.map((i) => i.name),
  datasets: [
    {
      label: '유상',
      data: shown.value.map((i) => i.paid),
      backgroundColor: paidColor('유상'),
      borderRadius: (ctx) => (shown.value[ctx.dataIndex]?.unpaid ? 0 : END_RADIUS),
    },
    { label: '무상', data: shown.value.map((i) => i.unpaid), backgroundColor: paidColor('무상'), borderRadius: END_RADIUS },
  ].map((d) => ({
    ...d,
    stack: 'paid',
    borderColor: '#ffffff', // 조각 사이 2px 흰 틈
    borderWidth: { left: 2 },
    borderSkipped: false,
    barThickness: 14,
  })),
}))

const options = computed(() => ({
  indexAxis: 'y',
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: { display: false }, // 위쪽 범례로 대신함
    tooltip: {
      callbacks: {
        label: (ctx) => `${ctx.dataset.label} ${ctx.raw}${props.unit}`,
        footer: (items) => {
          const i = shown.value[items[0].dataIndex]
          return `합계 ${i.quantity}${props.unit} · 무상 ${percent(i.unpaid, i.quantity)}%`
        },
      },
    },
  },
  scales: {
    x: { stacked: true, beginAtZero: true, ticks: { precision: 0 }, grid: { color: GRID_COLOR }, border: { display: false } },
    y: { stacked: true, grid: { display: false } },
  },
}))

const height = computed(() => `${Math.max(shown.value.length, 1) * 30 + 30}px`)
</script>

<template>
  <div>
    <p v-if="!items.length" class="text-muted small mb-0">데이터가 없습니다.</p>
    <template v-else>
      <div class="d-flex gap-3 small mb-1">
        <span v-for="name in ['유상', '무상']" :key="name">
          <span class="d-inline-block rounded-1 me-1 align-middle" :style="{ width: '10px', height: '10px', background: paidColor(name) }"></span>{{ name }}
        </span>
      </div>
      <div :style="{ height }">
        <Bar :data="chartData" :options="options" />
      </div>
      <!-- 값은 글자로도 보여준다 (색만으로 읽지 않게) -->
      <ol class="small text-muted mb-0 mt-1 ps-3">
        <li v-for="i in shown" :key="i.name">
          {{ i.name }} — {{ i.quantity.toLocaleString() }}{{ unit }} (유상 {{ i.paid }} · 무상 {{ i.unpaid }})
        </li>
      </ol>
      <p v-if="items.length > limit" class="text-muted small mb-0">상위 {{ limit }}개만 표시 (전체 {{ items.length }}개)</p>
    </template>
  </div>
</template>
