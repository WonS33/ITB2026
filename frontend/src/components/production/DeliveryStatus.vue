<script setup>
// 납기·출고: 왼쪽 = 납기 준수율(선택한 기간의 납기일 기준), 오른쪽 = 미출고 현황(오늘 기준)
// 상태는 색만으로 구분하지 않도록 기호(✓ ◐ !)와 글자를 함께 쓴다 (납기 캘린더와 같은 기호)
import { computed } from 'vue'
import { useRouter } from 'vue-router'

const props = defineProps({
  delivery: { type: Object, required: true }, // production/metrics.py delivery_performance
  unshipped: { type: Object, required: true }, // production/metrics.py unshipped_status
  label: { type: String, required: true }, // 선택한 기간 이름
})
const router = useRouter()

// 준수율 막대 조각: 기한 내 / 늦게 출고 / 미출고(납기 지남)
const PARTS = [
  { key: 'on_time', label: '✓ 기한 내 출고', color: '#4a7fc1' },
  { key: 'late', label: '◐ 늦게 출고', color: '#d9a066' },
  { key: 'open', label: '! 미출고(납기 지남)', color: '#c0392b' },
]
const d = computed(() => props.delivery)
const width = (n) => `${(n / d.value.total) * 100}%`
const ranked = (rows) => rows.filter((r) => r.total).slice(0, 5)
const rateText = (r) => (r === null ? '-' : `${r}%`)
const openSerial = (serial) => router.push({ path: '/production/serials', query: { q: serial } })
const maxBucket = computed(() => Math.max(1, ...props.unshipped.buckets.map((b) => b.count)))
</script>

<template>
  <div class="row g-3 mb-4">
    <!-- 납기 준수율 -->
    <div class="col-lg-6">
      <div class="card h-100"><div class="card-body">
        <h3 class="h6 mb-1">{{ label }} 납기 준수율 <span class="text-muted fw-normal small">· 납기일이 이 기간에 있고 이미 지난 제품</span></h3>
        <p v-if="!d.total" class="text-muted small mb-0 mt-2">
          아직 납기가 온 제품이 없습니다<template v-if="d.not_due_yet"> (납기 전 {{ d.not_due_yet }}대)</template>.
        </p>
        <template v-else>
          <div class="d-flex align-items-baseline gap-3 mt-2 mb-2">
            <div class="display-6 fw-semibold lh-1">{{ d.rate }}<span class="fs-6 fw-normal">%</span></div>
            <div class="small text-muted">
              {{ d.total }}대 중 {{ d.on_time }}대 기한 내 출고
              <template v-if="d.avg_delay_days !== null"><br />늦은 {{ d.late + d.open }}대의 평균 지연 {{ d.avg_delay_days }}일</template>
            </div>
          </div>
          <div class="d-flex rounded overflow-hidden mb-1" style="height: 12px" role="img" :aria-label="`기한 내 ${d.on_time}대, 늦게 출고 ${d.late}대, 미출고 ${d.open}대`">
            <div v-for="p in PARTS" :key="p.key" :style="{ width: width(d[p.key]), background: p.color }" class="part"></div>
          </div>
          <div class="d-flex flex-wrap gap-3 small mb-3">
            <span v-for="p in PARTS" :key="p.key">
              <span class="d-inline-block rounded-1 me-1 align-middle" :style="{ width: '10px', height: '10px', background: p.color }"></span>{{ p.label }} {{ d[p.key] }}
            </span>
            <span v-if="d.not_due_yet" class="text-muted">· 납기 전 {{ d.not_due_yet }}대 제외</span>
          </div>

          <div class="row g-3">
            <div v-for="[title, rows] in [['모델별', d.by_model], ['거래처별', d.by_customer]]" :key="title" class="col-sm-6">
              <div class="small fw-semibold mb-1">{{ title }} <span class="text-muted fw-normal">· 준수율 낮은 순</span></div>
              <table class="table table-sm small mb-0">
                <tbody>
                  <tr v-for="r in ranked(rows)" :key="r.name">
                    <td class="text-break">{{ r.name }}</td>
                    <td class="text-end text-nowrap">{{ rateText(r.rate) }}</td>
                    <td class="text-end text-nowrap text-muted">{{ r.on_time }}/{{ r.total }}대</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </template>
        <p class="text-muted small mt-2 mb-0">처리 완료 = 출고로 봅니다(기업 확인 필요). 제조내역 1행 = 1대 기준.</p>
      </div></div>
    </div>

    <!-- 미출고 현황 -->
    <div class="col-lg-6">
      <div class="card h-100"><div class="card-body">
        <h3 class="h6 mb-1">미출고 현황 <span class="text-muted fw-normal small">· {{ unshipped.as_of }} 기준, 기간 선택과 관계없음</span></h3>
        <div class="d-flex align-items-baseline gap-2 mt-2 mb-2">
          <div class="display-6 fw-semibold lh-1">{{ unshipped.total.toLocaleString() }}<span class="fs-6 fw-normal ms-1">대</span></div>
          <div class="small text-muted">제조했지만 아직 출고되지 않은 제품</div>
        </div>
        <template v-if="unshipped.total">
          <!-- 제조 후 지난 날수 구간 -->
          <div class="small mb-3">
            <div v-for="b in unshipped.buckets" :key="b.label" class="d-flex align-items-center gap-2 mb-1">
              <span class="text-nowrap" style="width: 5.5rem">{{ b.label }}</span>
              <div class="flex-grow-1"><div class="bucket" :style="{ width: `${(b.count / maxBucket) * 100}%` }"></div></div>
              <span class="text-nowrap text-end" style="width: 3rem">{{ b.count }}대</span>
            </div>
          </div>
          <div class="small fw-semibold mb-1">가장 오래된 미출고 <span class="text-muted fw-normal">· 누르면 일련번호 상세</span></div>
          <table class="table table-sm table-hover small mb-2">
            <thead><tr><th>일련번호</th><th>모델</th><th>제조</th><th class="text-end">경과</th><th>납기일</th></tr></thead>
            <tbody>
              <tr v-for="r in unshipped.oldest" :key="r.serial_full" role="button" @click="openSerial(r.serial_full)">
                <td class="text-nowrap">{{ r.serial_full }}</td>
                <td class="text-nowrap">{{ r.model_name || '-' }}</td>
                <td class="text-nowrap">{{ r.manufactured_date }}</td>
                <td class="text-end text-nowrap">{{ r.days }}일</td>
                <td class="text-nowrap">{{ r.due_date || '-' }}</td>
              </tr>
            </tbody>
          </table>
          <div class="small text-muted">
            모델별: <span v-for="(m, i) in unshipped.by_model" :key="m.name">{{ i ? ' · ' : '' }}{{ m.name }} {{ m.quantity }}대</span>
          </div>
        </template>
        <p class="text-muted small mt-2 mb-0">경과 = 오늘 − 제조년월(날짜). 출고일이 비어 있는 제품을 미출고로 셉니다.</p>
      </div></div>
    </div>
  </div>
</template>

<style scoped>
.part + .part {
  border-left: 2px solid #ffffff; /* 조각 사이 흰 틈 */
}
.bucket {
  height: 10px;
  min-width: 2px;
  background: #9aa9bd;
  border-radius: 0 4px 4px 0;
}
</style>
