<script setup>
// 순위 가로 막대그래프: 많은 순서대로 상위 limit개, 막대 끝에 "n대 (xx%)" 표시
import { computed } from 'vue'
import { Bar } from 'vue-chartjs'
import { GRID_COLOR, percent, SERIES_COLORS } from '@/charts'

const props = defineProps({
  items: { type: Array, required: true }, // [{ name, quantity }] (많은 순서)
  total: { type: Number, required: true },
  unit: { type: String, default: '대' },
  limit: { type: Number, default: 10 },
  color: { type: String, default: SERIES_COLORS[0] },
})

const shown = computed(() => props.items.slice(0, props.limit))
const label = (q) => `${q.toLocaleString()}${props.unit} (${percent(q, props.total)}%)`

const chartData = computed(() => ({
  labels: shown.value.map((i) => i.name),
  datasets: [
    {
      data: shown.value.map((i) => i.quantity),
      backgroundColor: shown.value.map((i) => i.color || props.color),
      borderRadius: 4,
      borderSkipped: 'start', // 둥근 끝은 막대 끝에만
      barThickness: 14,
    },
  ],
}))

const options = computed(() => ({
  indexAxis: 'y',
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  plugins: {
    legend: { display: false }, // 계열이 하나라 범례 없음 (제목이 이름을 대신함)
    tooltip: { callbacks: { label: (ctx) => label(ctx.raw) } },
  },
  scales: {
    x: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: GRID_COLOR }, border: { display: false } },
    y: { grid: { display: false } },
  },
}))

const height = computed(() => `${Math.max(shown.value.length, 1) * 30 + 30}px`)
</script>

<template>
  <div>
    <p v-if="!items.length" class="text-muted small mb-0">데이터가 없습니다.</p>
    <template v-else>
      <div :style="{ height }">
        <Bar :data="chartData" :options="options" />
      </div>
      <!-- 값은 글자로도 보여준다 (색만으로 읽지 않게) -->
      <ol class="small text-muted mb-0 mt-1 ps-3">
        <li v-for="i in shown" :key="i.name">{{ i.name }} — {{ label(i.quantity) }}</li>
      </ol>
      <p v-if="items.length > limit" class="text-muted small mb-0">상위 {{ limit }}개만 표시 (전체 {{ items.length }}개)</p>
    </template>
  </div>
</template>
