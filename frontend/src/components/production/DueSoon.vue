<script setup>
// 생산팀 대시보드 "납기 임박": 출고가 끝나지 않은 수주 중 납기 지남(최근 30일) + 오늘부터 14일 안
// 기간 선택과 관계없이 항상 오늘 기준으로 보여준다
import { onMounted, ref } from 'vue'
import { getDueSoon } from '@/api/production'
import { DUE_STATUS, dDayText, statusKey } from '@/dueStatus'

const data = ref(null)
const error = ref('')

onMounted(async () => {
  try {
    data.value = await getDueSoon()
  } catch (e) {
    error.value = e.message
  }
})

const orderLabel = (o) => (o.po_no ? `#${o.po_no}` : '수주번호 없음')
const month = (iso) => Number(iso.slice(5, 7))
const year = (iso) => Number(iso.slice(0, 4))
// D-day 배지 색: 지남 = 빨강, 3일 안 = 주황, 그 외 = 회색
const dDayClass = (d) => (d < 0 ? 'due-overdue' : d <= 3 ? 'due-partial' : 'due-done')
</script>

<template>
  <div class="card mb-3">
    <div class="card-body">
      <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-2">
        <h3 class="h6 mb-0">
          납기 임박
          <span v-if="data" class="text-muted fw-normal small">· 오늘부터 {{ data.days }}일 안 + 납기 지남, 출고가 끝나지 않은 수주 {{ data.items.length }}건</span>
        </h3>
        <RouterLink to="/production/calendar" class="small">납기 캘린더 →</RouterLink>
      </div>
      <div v-if="error" class="alert alert-danger py-2 mb-0">{{ error }}</div>
      <p v-else-if="data && !data.items.length" class="text-muted small mb-0">
        {{ data.days }}일 안에 납기가 돌아오는 미출고 수주가 없습니다.
      </p>
      <div v-else-if="data" class="table-responsive" style="max-height: 280px">
        <table class="table table-sm table-hover small align-middle mb-0">
          <thead class="table-light sticky-top">
            <tr><th>D-day</th><th>납기일</th><th>수주번호</th><th>판매처</th><th>사업명</th><th class="text-end">출고 / 대수</th><th>상태</th></tr>
          </thead>
          <tbody>
            <tr v-for="o in data.items" :key="`${o.due_date}-${o.po_no}`">
              <td><span class="badge" :class="dDayClass(o.d_day)">{{ dDayText(o.d_day) }}</span></td>
              <td class="text-nowrap">
                <RouterLink :to="{ path: '/production/calendar', query: { year: year(o.due_date), month: month(o.due_date), date: o.due_date } }">
                  {{ o.due_date }}
                </RouterLink>
              </td>
              <td class="text-nowrap">{{ orderLabel(o) }}</td>
              <td>{{ o.customers.join(', ') || '-' }}</td>
              <td>{{ o.projects.join(', ') || '-' }}</td>
              <td class="text-end text-nowrap">{{ o.shipped }} / {{ o.quantity }}대</td>
              <td class="text-nowrap">
                <span class="badge" :class="DUE_STATUS[statusKey(o)].cls">{{ DUE_STATUS[statusKey(o)].icon }} {{ DUE_STATUS[statusKey(o)].label }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
