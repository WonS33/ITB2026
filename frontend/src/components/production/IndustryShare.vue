<script setup>
// 산업 분야별 판매 비중 도넛 + 범례 표(색·분야·대수·비중) — 분야마다 고정 색
import { computed } from 'vue'
import { Doughnut } from 'vue-chartjs'
import { industryColor, percent } from '@/charts'

const props = defineProps({
  items: { type: Array, required: true }, // [{ name, quantity }]
  total: { type: Number, required: true },
})

const chartData = computed(() => ({
  labels: props.items.map((i) => i.name),
  datasets: [
    {
      data: props.items.map((i) => i.quantity),
      backgroundColor: props.items.map((i) => industryColor(i.name)),
      borderColor: '#ffffff', // 조각 사이 2px 흰 틈
      borderWidth: 2,
    },
  ],
}))

const options = {
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  cutout: '60%',
  plugins: {
    legend: { display: false }, // 오른쪽 범례 표로 대신함
    tooltip: {
      callbacks: { label: (ctx) => `${ctx.label}: ${ctx.raw}대 (${percent(ctx.raw, props.total)}%)` },
    },
  },
}
</script>

<template>
  <div>
    <p v-if="!items.length" class="text-muted small mb-0">데이터가 없습니다.</p>
    <div v-else class="d-flex flex-wrap align-items-center gap-3">
      <div style="width: 180px; height: 180px">
        <Doughnut :data="chartData" :options="options" />
      </div>
      <table class="table table-sm small mb-0 w-auto">
        <thead>
          <tr><th>분야</th><th class="text-end">대수</th><th class="text-end">비중</th></tr>
        </thead>
        <tbody>
          <tr v-for="i in items" :key="i.name">
            <td>
              <span class="d-inline-block rounded-circle me-1 align-middle" :style="{ width: '10px', height: '10px', background: industryColor(i.name) }"></span>
              {{ i.name }}
            </td>
            <td class="text-end">{{ i.quantity.toLocaleString() }}</td>
            <td class="text-end">{{ percent(i.quantity, total) }}%</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
