<script setup>
// 부품 단가 입력 — 서비스팀 수정 권한자만 (라우터에서 막고, 백엔드 API에서도 다시 확인함)
// 단가가 바뀌면 기존 줄을 고치지 않고 새 적용 시작일로 한 줄을 더한다 → 기간별 변동이 남는다
import { computed, onMounted, reactive, ref } from 'vue'
import { addPartPrice, deletePartPrice, getPartPrices } from '@/api/service'

const data = ref(null)
const error = ref('')
const message = ref('')
const errors = ref({})
const form = reactive({ part_name: '', unit_price: '', effective_date: new Date().toLocaleDateString('sv-SE') })

async function load() {
  try {
    data.value = await getPartPrices()
  } catch (e) {
    error.value = e.message
  }
}

const history = computed(() => data.value?.parts.find((p) => p.part_name === form.part_name)?.history ?? [])
const unregistered = computed(() => new Set(data.value?.unregistered.map((u) => u.part_name)))

async function submit() {
  errors.value = {}
  message.value = ''
  try {
    await addPartPrice({ ...form, unit_price: Number(form.unit_price) })
    message.value = `${form.part_name} ${Number(form.unit_price).toLocaleString()}원 (${form.effective_date}부터)을 저장했습니다.`
    form.unit_price = ''
    await load()
  } catch (e) {
    errors.value = e.data && typeof e.data === 'object' ? e.data : { detail: [e.message] }
  }
}

async function remove(h) {
  if (!confirm(`${form.part_name} ${h.unit_price.toLocaleString()}원 (${h.effective_date}부터) 줄을 삭제할까요?`)) return
  try {
    await deletePartPrice(h.id)
    await load()
  } catch (e) {
    error.value = e.message
  }
}

const list = (v) => (Array.isArray(v) ? v : v ? [v] : [])
onMounted(load)
</script>

<template>
  <div>
    <div v-if="error" class="alert alert-danger">{{ error }}</div>
    <div class="card mb-3" style="max-width: 760px"><div class="card-body">
      <h2 class="h6">부품 단가 입력</h2>
      <p class="text-muted small">
        부품명은 출장보고서에 나온 이름에서 고릅니다(이름이 같아야 사용 내역과 연결됨). 단가가 바뀌면 새 적용 시작일로 한 줄을 더 입력하세요.
      </p>
      <form v-if="data" class="row g-2" @submit.prevent="submit">
        <div class="col-md-5">
          <label class="form-label small mb-1" for="part">부품명</label>
          <select id="part" v-model="form.part_name" class="form-select form-select-sm" :class="{ 'is-invalid': errors.part_name }" required>
            <option value="">선택</option>
            <option v-for="name in data.part_names" :key="name" :value="name">
              {{ name }}{{ unregistered.has(name) ? ' (단가 없음)' : '' }}
            </option>
          </select>
          <div v-for="m in list(errors.part_name)" :key="m" class="invalid-feedback">{{ m }}</div>
        </div>
        <div class="col-6 col-md-3">
          <label class="form-label small mb-1" for="price">단가(원)</label>
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
        <div class="col-md-1">
          <label class="form-label small mb-1 d-none d-md-block">&nbsp;</label>
          <button class="btn btn-primary btn-sm w-100">저장</button>
        </div>
      </form>
      <div v-for="m in list(errors.detail)" :key="m" class="alert alert-danger py-2 mt-2 mb-0">{{ m }}</div>
      <div v-if="message" class="alert alert-success py-2 mt-2 mb-0">{{ message }}</div>
    </div></div>

    <div v-if="form.part_name" class="card mb-3" style="max-width: 760px"><div class="card-body">
      <h2 class="h6">{{ form.part_name }} 단가 이력</h2>
      <p v-if="!history.length" class="text-muted small mb-0">아직 입력된 단가가 없습니다.</p>
      <table v-else class="table table-sm small mb-0 align-middle">
        <thead><tr><th>적용 시작일</th><th class="text-end">단가</th><th>출처</th><th></th></tr></thead>
        <tbody>
          <tr v-for="h in [...history].reverse()" :key="h.id">
            <td>{{ h.effective_date }} <span v-if="h.upcoming" class="badge bg-light text-dark border">예정</span></td>
            <td class="text-end">{{ h.unit_price.toLocaleString() }}원</td>
            <td class="text-muted">{{ h.source }}</td>
            <td class="text-end">
              <button type="button" class="btn btn-outline-danger btn-sm py-0" @click="remove(h)">삭제</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div></div>
  </div>
</template>
