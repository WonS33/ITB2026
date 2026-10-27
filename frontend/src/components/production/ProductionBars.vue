<script setup>
// 생산량 막대 + 목표 점선 (월별 1~12월 또는 분기별 1~4분기 — 막대 목록은 대시보드가 만들어 넘긴다)
// 선택한 기간에 속한 막대는 진하게, 벗어난 막대는 흐리게 (서비스팀 월별 출장 막대와 같은 방식)
// 막대(그 칸 어디든)를 누르면 select(막대의 value)를 알린다 → 대시보드가 그 달·분기 제조내역 목록으로 이동
import { computed } from 'vue'
import { Bar } from 'vue-chartjs'
import { GRID_COLOR } from '@/charts'

const props = defineProps({
  bars: { type: Array, required: true }, // [{ value, label, actual, selected, inProgress }]
  target: { type: Number, default: null }, // 막대 하나의 목표(월 목표 또는 분기 목표), 없으면 null
  targetName: { type: String, default: '월 목표' },
  unitName: { type: String, default: '달' }, // 툴팁 안내 "누르면 이 달 제조내역 목록"
})
const emit = defineEmits(['select'])

const FILL = '#4a7fc1' // 달성률 도넛의 생산량 색과 같게
const FADED = 'rgba(74,127,193,0.35)'
const TARGET_LINE = '#52514e'
const isSelected = (index) => !!props.bars[index]?.selected

const chartData = computed(() => ({
  // 아직 끝나지 않은 달·분기는 아래에 "진행 중"을 한 줄 더 붙인다 (목표보다 낮아 보여도 덜 끝난 것임을 알 수 있게)
  labels: props.bars.map((b) => (b.inProgress ? [b.label, '진행 중'] : b.label)),
  datasets: [
    {
      label: '생산량',
      data: props.bars.map((b) => b.actual),
      backgroundColor: props.bars.map((b) => (b.selected ? FILL : FADED)),
      borderRadius: { topLeft: 4, topRight: 4 },
      borderSkipped: false,
      maxBarThickness: 48,
    },
  ],
}))

// 선택한 기간의 달 뒤에 옅은 회색 띠 (막대보다 먼저 그려서 뒤에 깔림)
const selectedBand = {
  id: 'selectedBand',
  beforeDatasetsDraw(chart) {
    const { ctx, chartArea, scales } = chart
    const step = scales.x.width / props.bars.length
    ctx.save()
    ctx.fillStyle = '#eef1f5'
    props.bars.forEach((b, i) => {
      if (isSelected(i)) ctx.fillRect(scales.x.getPixelForValue(i) - step / 2, chartArea.top, step, chartArea.height)
    })
    ctx.restore()
  },
}

// 목표 가로 점선 (막대 위에 그림)
const targetLine = {
  id: 'targetLine',
  afterDatasetsDraw(chart) {
    if (props.target === null) return
    const { ctx, chartArea, scales } = chart
    const y = scales.y.getPixelForValue(props.target)
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
    if (elements.length) emit('select', props.bars[elements[0].index].value)
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
          if (props.target) {
            const diff = Math.round((items[0].raw - props.target) * 10) / 10
            const rate = Math.round((items[0].raw / props.target) * 1000) / 10
            lines.push(`${props.targetName} ${props.target}대 · ${diff >= 0 ? `+${diff}` : diff}대 (달성률 ${rate}%)`)
          }
          if (props.bars[items[0].dataIndex]?.inProgress) lines.push(`진행 중인 ${props.unitName} — 아직 끝나지 않아 낮게 보일 수 있음`)
          lines.push(`누르면 이 ${props.unitName} 제조내역 목록`)
          return lines
        },
      },
    },
  },
  scales: {
    // 목표선이 늘 보이도록 y축 최대값을 목표보다 조금 크게
    y: {
      beginAtZero: true,
      suggestedMax: props.target ? props.target * 1.15 : undefined,
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
    <Bar :data="chartData" :options="options" :plugins="[selectedBand, targetLine]" :aria-label="`생산량과 ${targetName}`" role="img" />
  </div>
</template>
