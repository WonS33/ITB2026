<script setup>
// 월별 생산량 막대 + 월 목표 점선 (선택한 연도 1~12월)
// 선택한 기간의 달은 진하게, 벗어난 달은 흐리게 (서비스팀 월별 출장 막대와 같은 방식)
// 막대(그 달 칸 어디든)를 누르면 select(월)을 알린다 → 대시보드가 그 달 제조내역 목록으로 이동
import { computed } from 'vue'
import { Bar } from 'vue-chartjs'
import { GRID_COLOR } from '@/charts'

const props = defineProps({
  months: { type: Array, required: true }, // [{ month, actual }]
  monthlyTarget: { type: Number, default: null }, // 월 목표(연간 ÷ 12), 없으면 null
  highlight: { type: Array, default: () => [] }, // 강조할 달 번호
})
const emit = defineEmits(['select'])

const FILL = '#4a7fc1' // 달성률 도넛의 생산량 색과 같게
const FADED = 'rgba(74,127,193,0.35)'
const TARGET_LINE = '#52514e'
const isSelected = (index) => props.highlight.includes(props.months[index]?.month)

const chartData = computed(() => ({
  labels: props.months.map((m) => `${m.month}월`),
  datasets: [
    {
      label: '생산량',
      data: props.months.map((m) => m.actual),
      backgroundColor: props.months.map((m, i) => (isSelected(i) ? FILL : FADED)),
      borderRadius: { topLeft: 4, topRight: 4 },
      borderSkipped: false,
      maxBarThickness: 28,
    },
  ],
}))

// 선택한 기간의 달 뒤에 옅은 회색 띠 (막대보다 먼저 그려서 뒤에 깔림)
const selectedBand = {
  id: 'selectedBand',
  beforeDatasetsDraw(chart) {
    const { ctx, chartArea, scales } = chart
    const step = scales.x.width / props.months.length
    ctx.save()
    ctx.fillStyle = '#eef1f5'
    props.months.forEach((m, i) => {
      if (isSelected(i)) ctx.fillRect(scales.x.getPixelForValue(i) - step / 2, chartArea.top, step, chartArea.height)
    })
    ctx.restore()
  },
}

// 월 목표 가로 점선 + 오른쪽 끝 글자 (막대 위에 그림)
const targetLine = {
  id: 'targetLine',
  afterDatasetsDraw(chart) {
    if (props.monthlyTarget === null) return
    const { ctx, chartArea, scales } = chart
    const y = scales.y.getPixelForValue(props.monthlyTarget)
    ctx.save()
    ctx.strokeStyle = TARGET_LINE
    ctx.lineWidth = 2
    ctx.setLineDash([6, 4])
    ctx.beginPath()
    ctx.moveTo(chartArea.left, y)
    ctx.lineTo(chartArea.right, y)
    ctx.stroke()
    ctx.restore()
  },
}

const options = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  interaction: { mode: 'index', intersect: false },
  onClick: (event, elements) => {
    if (elements.length) emit('select', props.months[elements[0].index].month)
  },
  onHover: (event, elements) => {
    event.native.target.style.cursor = elements.length ? 'pointer' : 'default'
  },
  plugins: {
    legend: { display: false }, // 위쪽 범례로 대신함
    tooltip: {
      callbacks: {
        label: (ctx) => `생산량 ${ctx.raw}대`,
        footer: (items) => {
          const lines = []
          if (props.monthlyTarget !== null) {
            const diff = Math.round((items[0].raw - props.monthlyTarget) * 10) / 10
            lines.push(`월 목표 ${props.monthlyTarget}대 · ${diff >= 0 ? `+${diff}` : diff}대`)
          }
          lines.push('누르면 이 달 제조내역 목록')
          return lines
        },
      },
    },
  },
  scales: {
    // 목표선이 늘 보이도록 y축 최대값을 목표보다 조금 크게
    y: {
      beginAtZero: true,
      suggestedMax: props.monthlyTarget ? props.monthlyTarget * 1.15 : undefined,
      ticks: { precision: 0 },
      grid: { color: GRID_COLOR },
      border: { display: false },
    },
    x: {
      grid: { display: false },
      ticks: {
        color: (ctx) => (isSelected(ctx.index) ? '#1f2328' : '#8a8f98'),
        font: (ctx) => ({ weight: isSelected(ctx.index) ? 'bold' : 'normal' }),
      },
    },
  },
}))
</script>

<template>
  <div style="height: 220px">
    <Bar :data="chartData" :options="options" :plugins="[selectedBand, targetLine]" aria-label="월별 생산량과 월 목표" role="img" />
  </div>
</template>
