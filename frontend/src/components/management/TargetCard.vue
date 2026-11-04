<script setup>
// 목표매출 달성률 카드 (조원 저장소 targetCardModel 을 옮김)
// 가운데: 월 보기 = 그 달(월 목표 = 분기 목표 ÷ 3 자동) / 분기 = 그 분기 / 연간 = 연간
// 아래: 분기별 실적·달성률 (확정된 달이 없으면 0.0% 대신 사실만, 끝났고 다 확정됐는데 미달이면 "▼ 미달") + 연간 진도
import { computed } from 'vue'
import { Doughnut } from 'vue-chartjs'
import { pctText, wonShort } from '@/money'

const props = defineProps({
  targets: { type: Object, default: null }, // 서버 summary.targets (목표가 없으면 null)
  period: { type: Object, required: true }, // { kind, year, months }
})

const FILL = '#2a78d6' // 실적
const TRACK = '#e6eaf0' // 남은 목표

const current = computed(() => {
  const t = props.targets
  if (!t) return null
  return props.period.kind === 'month' ? t.month : t.period
})
const centerLabel = computed(() => {
  const p = props.period
  if (p.kind === 'month') return `${p.months[0]}월 달성률`
  if (p.kind === 'quarter') return `${Math.floor((p.months[0] - 1) / 3) + 1}분기 달성률`
  return `${p.year}년 달성률`
})
const selectedQuarter = computed(() => (props.period.kind === 'year' ? null : Math.floor((props.period.months[0] - 1) / 3) + 1))

const chartData = computed(() => {
  const c = current.value
  const filled = Math.min(c.actual, c.target)
  return {
    labels: ['실적', '남은 목표'],
    datasets: [{ data: [filled, Math.max(c.target - c.actual, 0)], backgroundColor: [FILL, TRACK], borderColor: '#ffffff', borderWidth: 2 }],
  }
})
const options = {
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  cutout: '72%',
  plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => `${ctx.label} ${ctx.raw.toLocaleString()}원` } } },
}

// 월 보기: 분기 첫 달 ~ 그 달 누적의 분기 진행률
const quarterProgress = computed(() => {
  if (props.period.kind !== 'month' || !props.targets) return null
  const m = props.period.months[0]
  const q = Math.floor((m - 1) / 3) + 1
  return { label: `${q}분기 진행률 (${(q - 1) * 3 + 1}~${m}월)`, rate: props.targets.period.rate }
})
</script>

<template>
  <div class="card h-100">
    <div class="card-body">
      <h3 class="h6 mb-3">목표매출 달성률</h3>
      <div v-if="!current || !current.target" class="text-muted small">
        {{ period.year }}년 목표가 설정되지 않았습니다.
        <RouterLink to="/management/settings">목표·항목 설정 →</RouterLink>
      </div>
      <template v-else>
        <div class="ring mx-auto">
          <Doughnut :data="chartData" :options="options" />
          <div class="ring-center">
            <div class="ring-value">{{ pctText(current.rate) }}</div>
            <div class="small text-muted">{{ centerLabel }}</div>
          </div>
        </div>
        <p class="small text-center mt-2 mb-1">목표 {{ wonShort(current.target) }} · 실적 {{ wonShort(current.actual) }}</p>
        <p v-if="period.kind === 'month'" class="small text-muted text-center mb-1">월 목표 = 분기 목표 ÷ 3 (자동)</p>
        <p v-if="quarterProgress" class="small fw-semibold text-center mb-1">{{ quarterProgress.label }} {{ pctText(quarterProgress.rate) }}</p>

        <ul class="list-unstyled small mt-3 mb-0" aria-label="분기별 목표 달성">
          <li v-for="q in targets.quarters" :key="q.quarter" class="d-flex justify-content-between gap-2 py-1 border-top"
              :class="{ 'fw-semibold': q.quarter === selectedQuarter }">
            <span class="text-nowrap">{{ q.quarter }}분기<span v-if="q.source === 'allocated'" class="text-muted fw-normal"> (자동 배분)</span></span>
            <span class="text-end">
              <template v-if="q.state === 'future'">-</template>
              <template v-else-if="q.no_confirmed_text">{{ q.no_confirmed_text }}</template>
              <template v-else>{{ wonShort(q.actual) }} / {{ wonShort(q.target) }} · {{ pctText(q.rate) }}</template>
              <span v-if="q.state === 'current'" class="badge badge-soft ms-1">진행 중</span>
              <span v-if="q.unconfirmed_months.length && !q.no_confirmed_text" class="badge badge-soft ms-1">{{ q.unconfirmed_months.join('·') }}월 미확정</span>
              <span v-if="q.warn" class="badge badge-low ms-1">▼ 미달</span>
            </span>
          </li>
        </ul>
        <!-- 연간 진도: 확정된 마지막 달 ÷ 12 를 경과율로 비교 (연간 보기는 가운데가 이미 연간) -->
        <p v-if="period.kind !== 'year'" class="small mt-2 mb-0">
          연간 {{ pctText(targets.annual.rate) }} · 경과율 {{ pctText(targets.annual.elapsed) }} ·
          <strong>진도 대비 {{ targets.annual.gap > 0 ? '▲' : targets.annual.gap < 0 ? '▼' : '' }}{{ Math.abs(targets.annual.gap).toFixed(1) }}%p
            {{ targets.annual.gap > 0 ? '앞섬' : targets.annual.gap < 0 ? '뒤처짐' : '' }}</strong>
        </p>
      </template>
    </div>
  </div>
</template>

<style scoped>
.ring {
  position: relative;
  width: 180px;
  height: 180px;
}
.ring-center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}
.ring-value {
  font-size: 1.6rem;
  font-weight: 700;
}
</style>
