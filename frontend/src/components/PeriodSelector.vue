<script setup>
// 기간 선택 영역: 연도 선택 + [당월 / 분기 / 연간] 전환 + (당월) 월 선택 / (분기) 1~4분기 선택
import { onMounted } from 'vue'
import { loadYearRange, period, PERIOD_KINDS, yearOptions as years } from '@/period'

// 연도 목록은 데이터에 맞춘다: 가장 이른 데이터 연도(없으면 3년 전) ~ 내년
onMounted(loadYearRange)
const months = Array.from({ length: 12 }, (_, i) => i + 1)
</script>

<template>
  <div class="d-flex flex-wrap align-items-center gap-2 mb-4">
    <select v-model.number="period.year" class="form-select form-select-sm w-auto" aria-label="연도">
      <option v-for="y in years" :key="y" :value="y">{{ y }}년</option>
    </select>

    <div class="btn-group btn-group-sm" role="group" aria-label="기간 보기">
      <button
        v-for="k in PERIOD_KINDS"
        :key="k.value"
        type="button"
        class="btn"
        :class="period.kind === k.value ? 'btn-primary' : 'btn-outline-primary'"
        @click="period.kind = k.value"
      >
        {{ k.label }}
      </button>
    </div>

    <select
      v-if="period.kind === 'month'"
      v-model.number="period.month"
      class="form-select form-select-sm w-auto"
      aria-label="월"
    >
      <option v-for="m in months" :key="m" :value="m">{{ m }}월</option>
    </select>

    <div v-if="period.kind === 'quarter'" class="btn-group btn-group-sm" role="group" aria-label="분기">
      <button
        v-for="q in 4"
        :key="q"
        type="button"
        class="btn"
        :class="period.quarter === q ? 'btn-secondary' : 'btn-outline-secondary'"
        @click="period.quarter = q"
      >
        {{ q }}분기
      </button>
    </div>
  </div>
</template>
