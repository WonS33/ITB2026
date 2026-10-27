<script setup>
// 교체 부품 단가 표: 현재 단가, 직전 단가 대비 증감, 단가 이력, 단가 미등록 부품
import { computed, onMounted, ref } from 'vue'
import PriceHistoryChart from '@/components/service/PriceHistoryChart.vue'
import { canEdit } from '@/auth'
import { getPartPrices } from '@/api/service'

const data = ref(null)
const error = ref('')
const selected = ref('') // 이력을 볼 부품명

async function load() {
  error.value = ''
  try {
    data.value = await getPartPrices()
    selected.value = selected.value || data.value.parts[0]?.part_name || ''
  } catch (e) {
    error.value = e.message
  }
}

const selectedPart = computed(() => data.value?.parts.find((p) => p.part_name === selected.value))
const won = (v) => (v === null ? '-' : `${v.toLocaleString()}원`)
function changeText(p) {
  if (p.change === null) return '-'
  const sign = p.change > 0 ? '+' : ''
  return `${sign}${p.change.toLocaleString()}원${p.change_rate === null ? '' : ` (${sign}${p.change_rate}%)`}`
}

onMounted(load)
</script>

<template>
  <div>
    <div v-if="error" class="alert alert-danger">{{ error }}</div>
    <template v-if="data">
      <div class="card mb-3"><div class="card-body">
        <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-2">
          <h2 class="h6 mb-0">교체 부품 단가 <span class="text-muted fw-normal">· {{ data.parts.length }}개 부품</span></h2>
          <RouterLink v-if="canEdit('service')" to="/service/part-prices/input" class="btn btn-outline-primary btn-sm">단가 입력</RouterLink>
        </div>
        <p v-if="!data.parts.length" class="text-muted small mb-0">입력된 단가가 없습니다.</p>
        <div v-else class="table-responsive">
          <table class="table table-sm table-hover small mb-0 align-middle">
            <thead>
              <tr>
                <th>부품명</th>
                <th class="text-end">사용 횟수</th>
                <th class="text-end">현재 단가</th>
                <th>적용 시작일</th>
                <th class="text-end">직전 단가</th>
                <th class="text-end">증감</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="p in data.parts"
                :key="p.part_name"
                role="button"
                :class="{ 'table-primary': p.part_name === selected }"
                @click="selected = p.part_name"
              >
                <td>{{ p.part_name }}</td>
                <td class="text-end">{{ p.usage_count }}회</td>
                <td class="text-end fw-semibold">{{ won(p.current_price) }}</td>
                <td>
                  {{ p.current_since || '적용 전' }}
                  <div v-if="p.current_source" class="text-muted" style="font-size: 0.75rem">{{ p.current_source }}</div>
                </td>
                <td class="text-end">{{ won(p.previous_price) }}</td>
                <!-- 증감은 색만으로 구분하지 않고 +/- 기호를 함께 표시 -->
                <td class="text-end" :style="{ color: p.change > 0 ? '#c0392b' : p.change < 0 ? '#2563a8' : '' }">{{ changeText(p) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="text-muted small mt-2 mb-0">
          현재 단가 = 적용 시작일이 오늘 이전인 가장 최근 단가. 사용 횟수는 출장보고서 전체 기간 기준(보고서에 수량이 없어 1회씩 셈).
          행을 누르면 아래에 단가 이력이 나옵니다.
        </p>
      </div></div>

      <div v-if="selectedPart" class="card mb-3"><div class="card-body">
        <h2 class="h6">{{ selectedPart.part_name }} 단가 이력</h2>
        <PriceHistoryChart :history="selectedPart.history" />
        <p class="text-muted small mt-2">점: 단가가 바뀐 날. 속이 빈 점은 아직 적용 전(예정)인 단가입니다.</p>
        <!-- 견적 단가는 출장 거리·작업 강도 등에 따라 달라질 수 있어, 방문한 회사·사업명·비고를 함께 보여준다 -->
        <div class="table-responsive">
          <table class="table table-sm small mb-0 align-top">
            <thead>
              <tr>
                <th>적용 시작일</th>
                <th class="text-end">단가</th>
                <th>출처</th>
                <th>업체(방문한 회사)</th>
                <th>사업명</th>
                <th>비고</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="h in [...selectedPart.history].reverse()" :key="h.id">
                <td class="text-nowrap">
                  {{ h.effective_date }} <span v-if="h.upcoming" class="badge bg-light text-dark border">예정</span>
                </td>
                <td class="text-end text-nowrap">{{ h.unit_price.toLocaleString() }}원</td>
                <td class="text-nowrap text-muted">{{ h.source }}</td>
                <td>{{ h.company || '-' }}</td>
                <td>{{ h.project || '-' }}</td>
                <td style="white-space: pre-line">{{ h.note || '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="text-muted small mt-2 mb-0">견적서 단가는 출장 거리·작업 강도 등에 따라 달라질 수 있습니다. 업체·사업명·비고로 이유를 확인하세요.</p>
      </div></div>

      <div class="card mb-3"><div class="card-body">
        <h2 class="h6">단가 미등록 부품 <span class="text-muted fw-normal">· {{ data.unregistered.length }}개</span></h2>
        <p v-if="!data.unregistered.length" class="text-muted small mb-0">출장보고서에 나온 부품은 모두 단가가 있습니다.</p>
        <ul v-else class="list-unstyled small mb-0 row">
          <li v-for="u in data.unregistered" :key="u.part_name" class="col-md-6">
            {{ u.part_name }} <span class="text-muted">· {{ u.usage_count }}회</span>
          </li>
        </ul>
      </div></div>
    </template>
  </div>
</template>
