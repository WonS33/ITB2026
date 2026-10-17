<script setup>
// 월별 출장 횟수 (선택한 연도 1~12월). 지금 보고 있는 기간의 달은 진하게, 나머지는 연하게 강조한다.
import { computed } from 'vue'
import { Bar } from 'vue-chartjs'
import { GRID_COLOR, SERIES_COLORS } from '@/charts'

const props = defineProps({
  monthly: { type: Array, required: true }, // [{ month, count }]
  highlight: { type: Array, default: () => [] }, // 강조할 달 번호
})

const MUTED = '#b7d3f6' // 같은 파랑의 연한 단계 (색은 하나, 진하기로만 구분)

const chartData = computed(() => ({
  labels: props.monthly.map((m) => `${m.month}월`),
  datasets: [
    {
      data: props.monthly.map((m) => m.count),
      backgroundColor: props.monthly.map((m) => (props.highlight.includes(m.month) ? SERIES_COLORS[0] : MUTED)),
      borderRadius: 4,
      borderSkipped: 'start',
      maxBarThickness: 28,
    },
  ],
}))

const options = {
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => `${ctx.raw}회` } } },
  scales: {
    y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: GRID_COLOR }, border: { display: false } },
    x: { grid: { display: false } },
  },
}
</script>

<template>
  <div style="height: 220px">
    <Bar :data="chartData" :options="options" />
  </div>
</template>
