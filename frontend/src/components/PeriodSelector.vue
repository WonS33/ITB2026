<script setup>
// 기간 선택 영역: 연도 선택 + [당월 / 분기 / 연간] 전환 + (당월) 월 선택 / (분기) 1~4분기 선택
// 팀 화면 틀(TeamLayout)의 제목 오른쪽 자리(#page-actions)로 옮겨 보여준다.
import { onMounted } from 'vue'
import { loadYearRange, period, PERIOD_KINDS, yearOptions as years } from '@/period'

// 연도 목록은 데이터에 맞춘다: 가장 이른 데이터 연도(없으면 3년 전) ~ 내년
onMounted(loadYearRange)
const months = Array.from({ length: 12 }, (_, i) => i + 1)
</script>

<template>
  <Teleport to="#page-actions" defer>
    <div class="d-flex flex-wrap align-items-center gap-2">
      <select v-model.number="period.year" class="form-select pill-select" aria-label="연도">
        <option v-for="y in years" :key="y" :value="y">{{ y }}년</option>
      </select>

      <div class="segmented" role="group" aria-label="기간 보기">
        <button
          v-for="k in PERIOD_KINDS"
          :key="k.value"
          type="button"
          :class="{ active: period.kind === k.value }"
          :aria-pressed="period.kind === k.value"
          @click="period.kind = k.value"
        >
          {{ k.label }}
        </button>
      </div>

      <select v-if="period.kind === 'month'" v-model.number="period.month" class="form-select pill-select" aria-label="월">
        <option v-for="m in months" :key="m" :value="m">{{ m }}월</option>
      </select>

      <select v-if="period.kind === 'quarter'" v-model.number="period.quarter" class="form-select pill-select" aria-label="분기">
        <option v-for="q in 4" :key="q" :value="q">{{ q }}분기</option>
      </select>
    </div>
  </Teleport>
</template>
