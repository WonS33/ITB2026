<script setup>
// 생산량 달성률 도넛: 채워진 부분 = 기간 생산량, 남은 회색 부분 = 부족치, 가운데 = 달성률
// 목표를 넘으면 고리를 모두 채우고 "목표 초과 n대"를 글자로 알린다 (색만으로 읽지 않게 세부 수치를 옆에 함께 표시)
import { computed } from 'vue'
import { Doughnut } from 'vue-chartjs'

const props = defineProps({
  production: { type: Object, required: true }, // { actual, period_target, achievement_rate, shortfall, annual_target }
})

const FILL = '#4a7fc1' // 생산량 (차분한 파랑)
const TRACK = '#e6eaf0' // 남은 양 (같은 계열의 옅은 회색)

const p = computed(() => props.production)
const hasTarget = computed(() => p.value.period_target !== null && p.value.period_target > 0)
const over = computed(() => (hasTarget.value ? Math.max(p.value.actual - p.value.period_target, 0) : 0))
const fmt = (v) => (Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { maximumFractionDigits: 1 }))

const chartData = computed(() => {
  const filled = hasTarget.value ? Math.min(p.value.actual, p.value.period_target) : 0
  const rest = hasTarget.value ? Math.max(p.value.period_target - p.value.actual, 0) : 1
  return {
    labels: ['생산량', '부족치'],
    datasets: [{ data: [filled, rest], backgroundColor: [FILL, TRACK], borderColor: '#ffffff', borderWidth: 2 }],
  }
})

const options = {
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  cutout: '72%',
  plugins: {
    legend: { display: false },
    tooltip: { callbacks: { label: (ctx) => `${ctx.label} ${fmt(ctx.raw)}대` } },
  },
}
</script>

<template>
  <div class="d-flex flex-wrap align-items-center gap-4">
    <div class="ring" role="img" :aria-label="hasTarget ? `달성률 ${p.achievement_rate}%` : '목표 없음'">
      <Doughnut :data="chartData" :options="options" />
      <div class="ring-center">
        <template v-if="hasTarget">
          <div class="fs-3 fw-semibold lh-1">{{ p.achievement_rate }}<span class="fs-6 fw-normal">%</span></div>
          <div class="text-muted small">달성률</div>
        </template>
        <div v-else class="text-muted small">목표 없음</div>
      </div>
    </div>

    <!-- 세부 수치 -->
    <dl class="detail mb-0">
      <div>
        <dt><span class="swatch" :style="{ background: FILL }"></span>생산량</dt>
        <dd>{{ fmt(p.actual) }}대 <span class="text-muted small">제조년월 기준</span></dd>
      </div>
      <div>
        <dt><span class="swatch swatch-line"></span>기간 목표</dt>
        <dd>{{ hasTarget ? `${fmt(p.period_target)}대` : '-' }} <span class="text-muted small">연간 목표 ÷ 12 × 개월 수</span></dd>
      </div>
      <div v-if="over">
        <dt>✓ 목표 초과</dt>
        <dd class="fw-semibold">{{ fmt(over) }}대</dd>
      </div>
      <div v-else>
        <dt><span class="swatch" :style="{ background: TRACK }"></span>부족치</dt>
        <dd>{{ hasTarget ? `${fmt(p.shortfall)}대` : '-' }}</dd>
      </div>
    </dl>
  </div>
</template>

<style scoped>
.ring {
  position: relative;
  width: 170px;
  height: 170px;
}
.ring-center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none; /* 도넛에 마우스를 올리면 툴팁이 나오게 */
}
.detail > div {
  display: flex;
  gap: 0.75rem;
  align-items: baseline;
  padding: 0.3rem 0;
  border-bottom: 1px solid #eef0f3;
}
.detail dt {
  width: 6.5rem;
  font-weight: 500;
  color: #6b7280;
}
.detail dd {
  margin: 0;
  font-size: 1.05rem;
}
.swatch {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 2px;
  margin-right: 0.35rem;
}
.swatch-line {
  border: 2px solid #4a7fc1;
}
</style>
