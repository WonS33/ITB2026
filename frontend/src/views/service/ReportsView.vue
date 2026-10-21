<script setup>
// 서비스팀 출장보고서 목록 + 상세 (기간 선택은 대시보드와 같은 값을 함께 씀)
import PeriodSelector from '@/components/PeriodSelector.vue'
import TripReportList from '@/components/service/TripReportList.vue'
</script>

<template>
  <div>
    <PeriodSelector />
    <TripReportList />
  </div>
</template>
