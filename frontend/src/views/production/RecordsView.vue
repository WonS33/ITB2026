<script setup>
// 제조내역 목록 (specs/05-production.md 7절): 기간(제조년월) 안의 제조내역을 표로 훑어본다
// 줄을 누르면 일련번호 조회 화면에서 그 제품의 상세를 연다. 걸러 낸 목록은 엑셀로 내려받을 수 있다.
import { reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PeriodSelector from '@/components/PeriodSelector.vue'
import ListPager from '@/components/ListPager.vue'
import { exportRecords, getRecords } from '@/api/production'
import { period } from '@/period'

const route = useRoute()
const router = useRouter()

// 대시보드 모델 도넛에서 넘어오면 ?model=NTI-04 로 걸러진 채 시작
const filters = reactive({ q: '', model: route.query.model || '', shipped: '' })
const query = ref('') // 검색 칸에 입력 중인 값 (검색 버튼을 눌러야 반영)
const page = ref(1)
const data = ref(null)
const error = ref('')
const exporting = ref(false)

async function load() {
  error.value = ''
  try {
    data.value = await getRecords(period, filters, page.value)
  } catch (e) {
    error.value = e.message
  }
}

// 기간·조건이 바뀌면 첫 쪽부터 다시
watch([period, filters], () => (page.value === 1 ? load() : (page.value = 1)), { deep: true })
watch(page, load, { immediate: true })

function search() {
  filters.q = query.value.trim()
}

async function download() {
  exporting.value = true
  error.value = ''
  try {
    await exportRecords(period, filters)
  } catch (e) {
    error.value = e.message
  } finally {
    exporting.value = false
  }
}

const SHIPPED = [
  { value: '', label: '전체', count: 'total' },
  { value: 'yes', label: '✓ 출고 완료', count: 'shipped' },
  { value: 'no', label: '○ 출고 전', count: 'not_shipped' },
]
const openSerial = (serial) => router.push({ path: '/production/serials', query: { q: serial } })
const month = (d) => (d ? d.slice(0, 7) : '-')
</script>

<template>
  <div>
    <PeriodSelector />

    <div class="card mb-4"><div class="card-body">
      <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
        <h2 class="h6 mb-0">
          제조내역 <span v-if="data" class="text-muted fw-normal">· {{ data.period.label }} · 제조년월 기준 {{ data.counts.total.toLocaleString() }}대</span>
        </h2>
        <button type="button" class="btn btn-outline-primary btn-sm" :disabled="exporting || !data?.total" @click="download">
          {{ exporting ? '만드는 중…' : '엑셀 내려받기' }}
        </button>
      </div>

      <!-- 걸러내기: 검색어 · 모델 · 출고 상태 -->
      <div class="d-flex flex-wrap align-items-center gap-2 mb-3">
        <form class="d-flex gap-2" @submit.prevent="search">
          <input v-model="query" class="form-control form-control-sm" style="width: 260px" placeholder="일련번호·거래처·사업명·PO번호" aria-label="검색어" />
          <button class="btn btn-primary btn-sm text-nowrap">검색</button>
        </form>
        <select v-model="filters.model" class="form-select form-select-sm w-auto" aria-label="모델">
          <option value="">모든 모델</option>
          <option v-for="m in data?.model_names || []" :key="m" :value="m">{{ m }}</option>
          <option value="(미입력)">(미입력)</option>
        </select>
        <div class="btn-group btn-group-sm" role="group" aria-label="출고 상태">
          <button
            v-for="s in SHIPPED"
            :key="s.value"
            type="button"
            class="btn"
            :class="filters.shipped === s.value ? 'btn-secondary' : 'btn-outline-secondary'"
            :aria-pressed="filters.shipped === s.value"
            @click="filters.shipped = s.value"
          >{{ s.label }} <span v-if="data">{{ data.counts[s.count] }}</span></button>
        </div>
        <button v-if="filters.q || filters.model" type="button" class="btn btn-link btn-sm" @click="Object.assign(filters, { q: '', model: '' }); query = ''">
          조건 지우기
        </button>
      </div>

      <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
      <template v-if="data">
        <p v-if="!data.results.length" class="text-muted small mb-0">조건에 맞는 제조내역이 없습니다.</p>
        <div v-else class="table-responsive" style="max-height: 65vh">
          <table class="table table-sm table-hover small mb-0 align-middle">
            <thead class="table-light sticky-top">
              <tr>
                <th>일련번호</th><th>모델</th><th>제조년월</th><th>검사일자</th><th>거래처</th>
                <th>사업명</th><th>PO번호</th><th>납기일</th><th>출고</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in data.results" :key="r.serial_full" role="button" title="일련번호 조회에서 상세 보기" @click="openSerial(r.serial_full)">
                <td class="fw-semibold text-nowrap">{{ r.serial_full }}</td>
                <td class="text-nowrap">{{ r.model_name || '-' }}</td>
                <td class="text-nowrap">{{ month(r.manufactured_date) }}</td>
                <td class="text-nowrap">{{ r.inspection_date || '-' }}</td>
                <td>{{ r.customer || '-' }}</td>
                <td>{{ r.project_name || '-' }}</td>
                <td class="text-nowrap">{{ r.po_no ? `#${r.po_no}` : '-' }}</td>
                <td class="text-nowrap">{{ r.due_date || '-' }}</td>
                <!-- 출고 상태는 기호와 글자를 함께 (색만으로 구분하지 않음) -->
                <td class="text-nowrap">
                  <span v-if="r.shipped_date" class="text-muted">✓ {{ r.shipped_date }}</span>
                  <span v-else class="fw-semibold">○ 출고 전</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <ListPager :page="data.page" :page-size="data.page_size" :total="data.total" @change="page = $event" />
        <p class="text-muted small mt-2 mb-0">줄을 누르면 일련번호 조회 화면에서 11개 항목 상세를 엽니다. 엑셀에는 걸러 낸 목록 전체가 모든 열과 함께 담깁니다.</p>
      </template>
    </div></div>
  </div>
</template>
