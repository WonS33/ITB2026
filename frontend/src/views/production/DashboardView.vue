<script setup>
// 생산팀 대시보드: 납기 임박(오늘 기준) + 생산 실적(목표 대비) + 판매 실적
import { ref, watch } from 'vue'
import PeriodSelector from '@/components/PeriodSelector.vue'
import DueSoon from '@/components/production/DueSoon.vue'
import SalesSection from '@/components/production/SalesSection.vue'
import StatCard from '@/components/StatCard.vue'
import TargetForm from '@/components/production/TargetForm.vue'
import { period } from '@/period'
import { getDashboard } from '@/api/production'

const data = ref(null)
const error = ref('')

async function load() {
  error.value = ''
  try {
    data.value = await getDashboard(period)
  } catch (e) {
    error.value = e.message
  }
}

// 기간을 바꾸면 다시 불러온다
watch(period, load, { deep: true, immediate: true })
</script>

<template>
  <div>
    <!-- 납기 임박은 기간 선택과 관계없이 오늘 기준이라 기간 선택보다 위에 둔다 -->
    <DueSoon />
    <PeriodSelector />

    <div v-if="error" class="alert alert-danger">{{ error }}</div>
    <template v-if="data">
      <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
        <h3 class="h6 mb-0">{{ data.period.label }} 생산 실적</h3>
        <!-- 연간 목표: 모두 볼 수 있고, 수정 권한자에게만 [목표 수정] 버튼이 보인다 -->
        <TargetForm :year="period.year" @saved="load" />
      </div>
      <div class="row g-3 mb-2">
        <div class="col-6 col-lg-3">
          <StatCard title="생산량" :value="data.production.actual" unit="대" hint="제조년월 기준" />
        </div>
        <div class="col-6 col-lg-3">
          <StatCard title="기간 목표" :value="data.production.period_target" unit="대" hint="연간 목표 ÷ 12 × 개월 수" />
        </div>
        <div class="col-6 col-lg-3">
          <StatCard title="달성률" :value="data.production.achievement_rate" unit="%">
            <div v-if="data.production.achievement_rate !== null" class="progress mt-2" style="height: 6px">
              <div
                class="progress-bar"
                :class="data.production.achievement_rate >= 100 ? 'bg-success' : ''"
                :style="{ width: Math.min(data.production.achievement_rate, 100) + '%' }"
              ></div>
            </div>
          </StatCard>
        </div>
        <div class="col-6 col-lg-3">
          <StatCard title="부족치" :value="data.production.shortfall" unit="대" hint="목표 초과 시 0" />
        </div>
      </div>
      <p v-if="data.production.annual_target === null" class="text-muted small">
        연간 목표 생산량이 없어 달성률·부족치를 계산할 수 없습니다.
      </p>
      <p class="text-muted small">
        ※ 당월·분기 목표는 "연간 목표 ÷ 12 × 개월 수"로 나눈 임시 기준입니다 (기업 확인 필요).
      </p>

      <SalesSection :sales="data.sales" :label="data.period.label" />
    </template>
  </div>
</template>
