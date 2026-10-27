<script setup>
// 월별 출장 횟수를 유상·무상으로 쌓은 막대 (선택한 연도 1~12월).
// 지금 보고 있는 기간의 달은 원래 색, 벗어난 달은 같은 색을 반투명하게(색 = 유상·무상은 그대로 유지).
// 선택한 기간은 옅은 회색 바탕 띠 + 굵은 월 글자로도 표시한다.
import { computed } from 'vue'
import { Bar } from 'vue-chartjs'
import { GRID_COLOR, paidColor, percent } from '@/charts'

const props = defineProps({
  monthly: { type: Array, required: true }, // [{ month, count, paid, unpaid }]
  highlight: { type: Array, default: () => [] }, // 강조할 달 번호
})

const TOP_RADIUS = { topLeft: 4, topRight: 4 }
const isSelected = (index) => props.highlight.includes(props.monthly[index]?.month)
const OUTSIDE_ALPHA = 0.35 // 선택한 기간을 벗어난 달의 불투명도

// '#4a7fc1' → 'rgba(74,127,193,0.35)'
function faded(hex) {
  const n = parseInt(hex.slice(1), 16)
  return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${OUTSIDE_ALPHA})`
}
const colorsFor = (name) => props.monthly.map((m, i) => (isSelected(i) ? paidColor(name) : faded(paidColor(name))))

const chartData = computed(() => ({
  labels: props.monthly.map((m) => `${m.month}월`),
  datasets: [
    // 유상을 아래(기준선 쪽)에 두어 달마다 유상 높이를 바로 비교할 수 있게
    // 둥근 모서리는 쌓은 막대의 맨 위 조각에만 (유상 위에 무상이 없으면 유상이 맨 위)
    {
      label: '유상',
      data: props.monthly.map((m) => m.paid),
      backgroundColor: colorsFor('유상'),
      borderRadius: (ctx) => (props.monthly[ctx.dataIndex]?.unpaid ? 0 : TOP_RADIUS),
    },
    { label: '무상', data: props.monthly.map((m) => m.unpaid), backgroundColor: colorsFor('무상'), borderRadius: TOP_RADIUS },
  ].map((d) => ({
    ...d,
    stack: 'trips',
    borderColor: '#ffffff', // 쌓인 조각 사이 2px 흰 틈
    borderWidth: { top: 2 },
    borderSkipped: false,
    maxBarThickness: 28,
  })),
}))

// 선택한 기간의 달 뒤에 옅은 회색 띠를 그린다 (막대보다 먼저 그려서 뒤에 깔림)
const selectedBand = {
  id: 'selectedBand',
  beforeDatasetsDraw(chart) {
    const { ctx, chartArea, scales } = chart
    const step = scales.x.width / props.monthly.length
    ctx.save()
    ctx.fillStyle = '#eef1f5'
    props.monthly.forEach((m, i) => {
      if (isSelected(i)) ctx.fillRect(scales.x.getPixelForValue(i) - step / 2, chartArea.top, step, chartArea.height)
    })
    ctx.restore()
  },
}

const options = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  interaction: { mode: 'index', intersect: false }, // 막대 근처 어디든 올리면 그 달 내용
  plugins: {
    legend: { display: false }, // 위쪽 범례로 대신함
    tooltip: {
      callbacks: {
        label: (ctx) => `${ctx.dataset.label} ${ctx.raw}회`,
        footer: (items) => {
          const m = props.monthly[items[0].dataIndex]
          return m.count ? `합계 ${m.count}회 · 유상 ${percent(m.paid, m.count)}%` : '출장 없음'
        },
      },
    },
  },
  scales: {
    y: { stacked: true, beginAtZero: true, ticks: { precision: 0 }, grid: { color: GRID_COLOR }, border: { display: false } },
    x: {
      stacked: true,
      grid: { display: false },
      // 선택한 기간의 월 글자만 진하고 굵게
      ticks: {
        color: (ctx) => (isSelected(ctx.index) ? '#1f2328' : '#8a8f98'),
        font: (ctx) => ({ weight: isSelected(ctx.index) ? 'bold' : 'normal' }),
      },
    },
  },
}))
</script>

<template>
  <div style="height: 240px">
    <Bar :data="chartData" :options="options" :plugins="[selectedBand]" aria-label="월별 출장 횟수 (유상·무상)" role="img" />
  </div>
</template>
