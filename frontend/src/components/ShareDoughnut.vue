<script setup>
// 비중 도넛 + 범례 표(색·이름·값·비중). 색은 colorOf(이름)으로 항목마다 고정한다.
// 표에 값을 글자로 함께 보여주므로 색만으로 읽지 않아도 된다.
import { computed } from 'vue'
import { Doughnut } from 'vue-chartjs'
import { percent } from '@/charts'

const props = defineProps({
  items: { type: Array, required: true }, // [{ name, quantity }]
  total: { type: Number, required: true },
  colorOf: { type: Function, required: true },
  nameHeader: { type: String, default: '항목' },
  unit: { type: String, default: '대' },
})

const shown = computed(() => props.items.filter((i) => i.quantity > 0))

const chartData = computed(() => ({
  labels: shown.value.map((i) => i.name),
  datasets: [
    {
      data: shown.value.map((i) => i.quantity),
      backgroundColor: shown.value.map((i) => props.colorOf(i.name)),
      borderColor: '#ffffff', // 조각 사이 2px 흰 틈
      borderWidth: 2,
    },
  ],
}))

const options = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  cutout: '60%',
  plugins: {
    legend: { display: false }, // 오른쪽 범례 표로 대신함
    tooltip: {
      callbacks: { label: (ctx) => `${ctx.label}: ${ctx.raw}${props.unit} (${percent(ctx.raw, props.total)}%)` },
    },
  },
}))
</script>

<template>
  <div>
    <p v-if="!shown.length" class="text-muted small mb-0">데이터가 없습니다.</p>
    <div v-else class="d-flex flex-wrap align-items-center gap-3">
      <div style="width: 180px; height: 180px">
        <Doughnut :data="chartData" :options="options" />
      </div>
      <table class="table table-sm small mb-0 w-auto">
        <thead>
          <tr><th>{{ nameHeader }}</th><th class="text-end">{{ unit === '회' ? '횟수' : '대수' }}</th><th class="text-end">비중</th></tr>
        </thead>
        <tbody>
          <tr v-for="i in items" :key="i.name">
            <td>
              <span class="d-inline-block rounded-circle me-1 align-middle" :style="{ width: '10px', height: '10px', background: colorOf(i.name) }"></span>
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
