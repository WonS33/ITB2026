<script setup>
// 뉴토크 기준값 대비 차이율(%) 가로 막대: 0(기준값)에서 오른쪽은 비쌈(빨강), 왼쪽은 쌈(파랑)
// 색만으로 읽지 않게 막대 옆 목록에 +/− 기호와 숫자를 함께 보여 준다
import { computed } from 'vue'
import { Bar } from 'vue-chartjs'
import { GRID_COLOR } from '@/charts'

const ABOVE_COLOR = '#e34948' // 기준값보다 비쌈
const BELOW_COLOR = '#2a78d6' // 기준값보다 쌈 (두 색 구분은 검증 도구로 확인 — 색약 포함)

const props = defineProps({
  items: { type: Array, required: true }, // [{ key, label, rate, detail }] — detail: 툴팁에 덧붙일 글자
  selected: { type: [String, Number], default: null },
})
const emit = defineEmits(['select'])

const signedRate = (r) => `${r > 0 ? '+' : ''}${r}%`
const colorOf = (i) => (i.rate > 0 ? ABOVE_COLOR : i.rate < 0 ? BELOW_COLOR : '#a3a29c')

const chartData = computed(() => ({
  labels: props.items.map((i) => i.label),
  datasets: [
    {
      data: props.items.map((i) => i.rate),
      backgroundColor: props.items.map((i) =>
        props.selected === null || props.selected === i.key ? colorOf(i) : `${colorOf(i)}55`),
      borderRadius: 4,
      borderSkipped: false,
      barThickness: 14,
    },
  ],
}))

// 0을 가운데 두도록 좌우 범위를 같게 (막대가 한쪽으로 쏠려도 기준선이 보이게)
const bound = computed(() => {
  const max = Math.max(5, ...props.items.map((i) => Math.abs(i.rate)))
  return Math.ceil(max / 5) * 5
})

const options = computed(() => ({
  indexAxis: 'y',
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  onClick: (_, elements) => {
    if (elements.length) emit('select', props.items[elements[0].index].key)
  },
  onHover: (e, elements) => {
    e.native.target.style.cursor = elements.length ? 'pointer' : 'default'
  },
  plugins: {
    legend: { display: false }, // 계열 하나 (색 뜻은 그래프 위 설명에)
    tooltip: {
      callbacks: {
        label: (ctx) => {
          const i = props.items[ctx.dataIndex]
          return [`기준값 대비 ${signedRate(i.rate)}`, ...(i.detail ? [i.detail] : [])]
        },
      },
    },
  },
  scales: {
    x: {
      min: -bound.value,
      max: bound.value,
      ticks: { callback: (v) => `${v > 0 ? '+' : ''}${v}%` },
      // 0% 선(= 뉴토크 기준값)만 진하게
      grid: { color: (ctx) => (ctx.tick.value === 0 ? '#52514e' : GRID_COLOR), lineWidth: (ctx) => (ctx.tick.value === 0 ? 1.5 : 1) },
      border: { display: false },
    },
    y: { grid: { display: false } },
  },
}))

const height = computed(() => `${Math.max(props.items.length, 1) * 28 + 40}px`)
</script>

<template>
  <div>
    <div class="d-flex flex-wrap gap-3 small text-muted mb-1">
      <span><span class="swatch" :style="{ background: BELOW_COLOR }"></span>기준값보다 쌈 (−)</span>
      <span><span class="swatch" :style="{ background: ABOVE_COLOR }"></span>기준값보다 비쌈 (+)</span>
      <span>가운데 진한 선 = 뉴토크 기준값 (0%)</span>
    </div>
    <div :style="{ height }">
      <Bar :data="chartData" :options="options" />
    </div>
  </div>
</template>

<style scoped>
.swatch {
  display: inline-block;
  width: 10px;
  height: 10px;
  margin-right: 4px;
  border-radius: 2px;
  vertical-align: -1px;
}
</style>
