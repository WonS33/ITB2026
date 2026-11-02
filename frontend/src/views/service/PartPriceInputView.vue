<script setup>
// 출장지 단가 입력 — 서비스팀 수정 권한자만 (라우터에서 막고, 백엔드 API에서도 다시 확인함)
// 파트넘버(단가표 부품)를 검색해 고르고, 출장지(업체)·단가·적용 시작일을 입력한다
// 같은 부품이라도 업체마다 따로 쌓이고, 교체부품 단가 화면에서 뉴토크 기준값·평균·최저·최고와 비교된다
import { computed, onMounted, reactive, ref } from 'vue'
import { addPartPrice, deletePartPrice, getCatalogChoices, getPartCatalogItem } from '@/api/service'

const choices = ref(null)
const detail = ref(null) // 고른 부품의 출장지별 단가
const error = ref('')
const message = ref('')
const errors = ref({})
const search = ref('') // 파트넘버 검색 칸 (목록에서 고르면 '파트넘버 품명 (적용 모델)'이 들어감)
const form = reactive({ unit_price: '', quote_company: '', effective_date: new Date().toLocaleDateString('sv-SE'), quote_note: '' })

onMounted(async () => {
  try {
    choices.value = await getCatalogChoices()
  } catch (e) {
    error.value = e.message
  }
})

// 검색 칸 글자와 정확히 같은 목록 항목 = 고른 부품
const selected = computed(() => choices.value?.items.find((i) => i.label === search.value) ?? null)
// 파트넘버를 하이픈 없이 쳐도 후보가 보이도록 (예: 0501 → XX-05-A-01)
const norm = (t) => (t || '').replace(/[\s-]/g, '').toUpperCase()
const candidates = computed(() => {
  const q = norm(search.value)
  if (!choices.value || !q || selected.value) return []
  return choices.value.items.filter((i) => norm(i.part_no).includes(q) || norm(i.part_no).replace(/\D/g, '').includes(q) || norm(i.name).includes(q)).slice(0, 12)
})

async function pick(item) {
  search.value = item.label
  await loadDetail()
}
async function loadDetail() {
  detail.value = selected.value ? await getPartCatalogItem(selected.value.id) : null
}

async function submit() {
  errors.value = {}
  message.value = ''
  if (!selected.value) {
    errors.value = { catalog_item: ['목록에서 파트넘버를 골라 주세요.'] }
    return
  }
  try {
    await addPartPrice({ ...form, catalog_item: selected.value.id, unit_price: Number(form.unit_price) })
    message.value = `${selected.value.part_no} ${form.quote_company} ${Number(form.unit_price).toLocaleString()}원 (${form.effective_date}부터)을 저장했습니다.`
    if (!choices.value.companies.includes(form.quote_company)) choices.value.companies.push(form.quote_company)
    form.unit_price = ''
    form.quote_note = ''
    await loadDetail()
  } catch (e) {
    errors.value = e.data && typeof e.data === 'object' ? e.data : { detail: [e.message] }
  }
}

async function remove(p) {
  if (!confirm(`${p.company} ${p.unit_price.toLocaleString()}원 (${p.effective_date}부터) 줄을 삭제할까요?`)) return
  try {
    await deletePartPrice(p.id)
    await loadDetail()
  } catch (e) {
    error.value = e.message
  }
}

const list = (v) => (Array.isArray(v) ? v : v ? [v] : [])
const won = (v) => (v === null || v === undefined ? '-' : `${v.toLocaleString()}원`)
</script>

<template>
  <div>
    <div v-if="error" class="alert alert-danger">{{ error }}</div>
    <div class="card mb-3" style="max-width: 860px"><div class="card-body">
      <h2 class="h6">출장지 단가 입력</h2>
      <p class="text-muted small">
        파트넘버를 검색해 고른 뒤 출장지(업체)와 단가를 입력하세요. 같은 업체의 단가가 바뀌면 새 적용 시작일로 한 줄을 더 입력합니다.
        견적서 PDF가 있으면 [견적서 업로드]로 한 번에 넣을 수 있습니다.
      </p>
      <form v-if="choices" class="row g-2" @submit.prevent="submit">
        <div class="col-12 position-relative">
          <label class="form-label small mb-1" for="part">파트넘버</label>
          <input id="part" v-model="search" class="form-control form-control-sm" :class="{ 'is-invalid': errors.catalog_item }"
                 placeholder="파트넘버(예: 05-A-01) 또는 품명을 입력해 목록에서 고르세요" autocomplete="off" @change="loadDetail" />
          <div v-for="m in list(errors.catalog_item)" :key="m" class="invalid-feedback">{{ m }}</div>
          <div v-if="candidates.length" class="list-group position-absolute w-100 shadow-sm candidates">
            <button v-for="c in candidates" :key="c.id" type="button" class="list-group-item list-group-item-action small py-1" @click="pick(c)">
              <strong>{{ c.part_no }}</strong> {{ c.name }} <span class="text-muted">{{ c.applies_to }}</span>
            </button>
          </div>
          <p v-if="!choices.items.length" class="text-danger small mt-1 mb-0">단가표가 없습니다. 관리자가 단가표를 먼저 넣어야 합니다.</p>
        </div>
        <div class="col-md-4">
          <label class="form-label small mb-1" for="company">출장지(업체)</label>
          <input id="company" v-model="form.quote_company" list="companies" class="form-control form-control-sm"
                 :class="{ 'is-invalid': errors.quote_company }" required />
          <datalist id="companies"><option v-for="c in choices.companies" :key="c" :value="c" /></datalist>
          <div v-for="m in list(errors.quote_company)" :key="m" class="invalid-feedback">{{ m }}</div>
        </div>
        <div class="col-6 col-md-3">
          <label class="form-label small mb-1" for="price">단가(원, 부가세 제외)</label>
          <input id="price" v-model="form.unit_price" type="number" min="0" step="1" class="form-control form-control-sm"
                 :class="{ 'is-invalid': errors.unit_price }" required />
          <div v-for="m in list(errors.unit_price)" :key="m" class="invalid-feedback">{{ m }}</div>
        </div>
        <div class="col-6 col-md-3">
          <label class="form-label small mb-1" for="since">적용 시작일</label>
          <input id="since" v-model="form.effective_date" type="date" class="form-control form-control-sm"
                 :class="{ 'is-invalid': errors.effective_date }" required />
          <div v-for="m in list(errors.effective_date)" :key="m" class="invalid-feedback">{{ m }}</div>
        </div>
        <div class="col-md-2">
          <label class="form-label small mb-1 d-none d-md-block">&nbsp;</label>
          <button class="btn btn-primary btn-sm w-100">저장</button>
        </div>
        <div class="col-12">
          <label class="form-label small mb-1" for="note">비고 (단가가 달라진 이유 등, 선택)</label>
          <input id="note" v-model="form.quote_note" class="form-control form-control-sm" />
        </div>
      </form>
      <div v-for="m in list(errors.detail)" :key="m" class="alert alert-danger py-2 mt-2 mb-0">{{ m }}</div>
      <div v-if="message" class="alert alert-success py-2 mt-2 mb-0">{{ message }}</div>
    </div></div>

    <div v-if="detail" class="card mb-3" style="max-width: 860px"><div class="card-body">
      <h2 class="h6">{{ detail.part_no }} {{ detail.name }} 출장지별 단가</h2>
      <p class="small mb-2">뉴토크 기준값 <strong>{{ won(detail.standard_price) }}</strong> · 평균 {{ won(detail.stats.average) }} · 최저 {{ won(detail.stats.min) }} · 최고 {{ won(detail.stats.max) }}</p>
      <p v-if="!detail.prices.length" class="text-muted small mb-0">아직 입력된 단가가 없습니다.</p>
      <table v-else class="table table-sm small mb-0 align-middle">
        <thead><tr><th>출장지(업체)</th><th>적용 시작일</th><th class="text-end">단가</th><th>출처</th><th></th></tr></thead>
        <tbody>
          <tr v-for="p in detail.prices" :key="p.id">
            <td>{{ p.company }}</td>
            <td>{{ p.effective_date }} <span v-if="p.upcoming" class="badge bg-light text-dark border">예정</span></td>
            <td class="text-end">{{ won(p.unit_price) }}</td>
            <td class="text-muted">{{ p.source }} {{ p.quote_no }}</td>
            <td class="text-end"><button type="button" class="btn btn-outline-danger btn-sm py-0" @click="remove(p)">삭제</button></td>
          </tr>
        </tbody>
      </table>
    </div></div>
  </div>
</template>

<style scoped>
.candidates {
  z-index: 10;
  max-height: 320px;
  overflow-y: auto;
}
</style>
