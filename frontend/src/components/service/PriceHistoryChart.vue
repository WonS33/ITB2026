<script setup>
// 부품 한 개의 단가 이력 (계단형 꺾은선: 단가는 다음 변경 전까지 그대로 유지되므로)
import { computed } from 'vue'
import { Line } from 'vue-chartjs'
import { GRID_COLOR, SERIES_COLORS } from '@/charts'

const props = defineProps({
  history: { type: Array, required: true }, // [{ unit_price, effective_date, upcoming }]
})

const won = (v) => `${v.toLocaleString()}원`

const chartData = computed(() => ({
  labels: props.history.map((h) => h.effective_date),
  datasets: [
    {
      data: props.history.map((h) => h.unit_price),
      borderColor: SERIES_COLORS[0],
      backgroundColor: SERIES_COLORS[0],
      borderWidth: 2,
      stepped: true,
      pointRadius: 5,
      pointHoverRadius: 7,
      pointBorderColor: SERIES_COLORS[0],
      pointBorderWidth: 2,
      // 아직 적용 전(예정)인 단가는 속이 빈 점으로 구분
      pointBackgroundColor: props.history.map((h) => (h.upcoming ? '#ffffff' : SERIES_COLORS[0])),
    },
  ],
}))

const options = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: { display: false },
    tooltip: {
      callbacks: {
        title: (items) => `${items[0].label}부터${props.history[items[0].dataIndex]?.upcoming ? ' (예정)' : ''}`,
        label: (ctx) => won(ctx.raw),
      },
    },
  },
  scales: {
    y: { beginAtZero: true, ticks: { callback: won }, grid: { color: GRID_COLOR }, border: { display: false } },
    x: { grid: { display: false } },
  },
}))
</script>

<template>
  <div style="height: 220px">
    <Line :data="chartData" :options="options" />
  </div>
</template>
