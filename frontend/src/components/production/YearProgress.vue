<script setup>
// 연간 목표까지 남은 양 + 연말 예상 생산량(예측)
// 예측값은 실제값과 섞이지 않게 점선 테두리 상자와 "예측" 표시로 따로 보여준다 (CLAUDE.md 6절)
import { computed } from 'vue'
import { percent } from '@/charts'

const props = defineProps({
  progress: { type: Object, required: true }, // backend production/metrics.py year_progress
})

const p = computed(() => props.progress)
const hasTarget = computed(() => p.value.annual_target !== null && p.value.annual_target > 0)
const rate = computed(() => (hasTarget.value ? percent(p.value.cumulative, p.value.annual_target) : 0))
const fmt = (v) => v.toLocaleString(undefined, { maximumFractionDigits: 1 })
</script>

<template>
  <div>
    <h3 class="h6 mb-2">
      {{ p.year }}년 연간 목표 진행
      <span v-if="p.as_of" class="text-muted fw-normal small">· {{ p.as_of }}까지</span>
    </h3>

    <template v-if="hasTarget">
      <div class="d-flex justify-content-between small mb-1">
        <span>누적 <strong>{{ fmt(p.cumulative) }}</strong> / {{ fmt(p.annual_target) }}대</span>
        <span>{{ rate }}%</span>
      </div>
      <div
        class="progress mb-2"
        style="height: 10px"
        role="progressbar"
        :aria-valuenow="Math.min(rate, 100)"
        aria-valuemin="0"
        aria-valuemax="100"
        :aria-label="`연간 목표 대비 누적 ${rate}%`"
      >
        <div class="progress-bar" :style="{ width: `${Math.min(rate, 100)}%`, background: '#4a7fc1' }"></div>
      </div>

      <p class="small mb-0">
        <template v-if="p.remaining === 0">✓ 연간 목표를 달성했습니다 (초과 {{ fmt(p.cumulative - p.annual_target) }}대).</template>
        <template v-else-if="p.remaining_months === 0">연간 목표에 {{ fmt(p.remaining) }}대 못 미쳤습니다.</template>
        <template v-else>
          남은 <strong>{{ fmt(p.remaining) }}대</strong> → 남은 {{ p.remaining_months }}개월<span v-if="p.is_current_year" class="text-muted">(이번 달 포함)</span>
          동안 <strong>월 평균 {{ fmt(p.required_per_month) }}대</strong> 필요
        </template>
      </p>
    </template>
    <p v-else class="text-muted small mb-0">
      누적 {{ fmt(p.cumulative) }}대 · 연간 목표가 없어 남은 양을 계산할 수 없습니다.
    </p>

    <!-- 연말 예상: 올해만 (지난 해는 이미 결과가 있고, 앞으로 올 해는 근거 데이터가 없음) -->
    <div v-if="p.forecast !== null" class="forecast mt-3">
      <div class="d-flex align-items-center gap-2 small">
        <span class="badge bg-light text-dark border">예측</span>
        <span>연말 예상 생산량 <strong>약 {{ fmt(p.forecast) }}대</strong></span>
        <span v-if="hasTarget" class="text-muted">
          (목표 대비 {{ p.forecast >= p.annual_target ? '+' : '' }}{{ fmt(p.forecast - p.annual_target) }}대)
        </span>
      </div>
      <div class="text-muted mt-1" style="font-size: 0.75rem">
        1월 1일부터 지금까지의 하루 평균 생산 속도가 연말까지 이어진다고 가정한 값입니다. 실제 결과와 다를 수 있습니다.
      </div>
    </div>
  </div>
</template>

<style scoped>
.forecast {
  border: 1px dashed #b8bec8;
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
}
</style>
