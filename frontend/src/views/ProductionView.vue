<script setup>
import { ref, watch } from 'vue'
import FileUpload from '@/components/FileUpload.vue'
import PeriodSelector from '@/components/PeriodSelector.vue'
import SerialSearch from '@/components/production/SerialSearch.vue'
import DueCalendar from '@/components/production/DueCalendar.vue'
import StatCard from '@/components/StatCard.vue'
import TargetForm from '@/components/production/TargetForm.vue'
import { canEdit } from '@/auth'
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
    <div class="d-flex align-items-center gap-2 mb-3">
      <h1 class="h4 mb-0">생산팀</h1>
      <span v-if="canEdit('production')" class="badge bg-primary">열람·수정</span>
      <span v-else class="badge bg-secondary">열람만</span>
    </div>
    <PeriodSelector />
    <TargetForm :year="period.year" @saved="load" />

    <div v-if="error" class="alert alert-danger">{{ error }}</div>
    <template v-if="data">
      <h2 class="h6 mb-3">{{ data.period.label }} 생산 실적</h2>
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
    </template>

    <SerialSearch />
    <DueCalendar />

    <!-- 업로드는 생산팀 수정 권한자에게만 보인다 (백엔드 API에서도 권한을 다시 확인함) -->
    <FileUpload
      v-if="canEdit('production')"
      kind="manufacturing_excel"
      title="제조내역 엑셀 업로드"
      accept=".xlsx"
      help="제조내역 엑셀(.xlsx)을 올리면 추출 결과를 먼저 보여줍니다. 확인·수정한 뒤 [저장]을 눌러야 반영됩니다. 이미 저장된 일련번호는 건너뜁니다."
      @saved="load"
    />
  </div>
</template>
