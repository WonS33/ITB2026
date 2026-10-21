<script setup>
// 요청처 지역 관리 — 서비스팀 수정 권한자만 (라우터에서 막고, 백엔드 API에서도 다시 확인함)
// 요청처 → 시·도·시·군 대응표를 고치면, 같은 요청처로 저장된 출장보고서의 지역도 함께 바뀐다
import { onMounted, reactive, ref } from 'vue'
import { getRequesterRegions, updateRequesterRegion } from '@/api/service'

const data = ref(null)
const drafts = reactive({}) // id → { region, district }
const rowErrors = reactive({}) // id → 메시지
const message = ref('')
const error = ref('')

async function load() {
  try {
    data.value = await getRequesterRegions()
    for (const r of data.value.results) drafts[r.id] = { region: r.region, district: r.district }
  } catch (e) {
    error.value = e.message
  }
}

const districtsOf = (region) => data.value.districts[region] || []
const changed = (r) => drafts[r.id].region !== r.region || drafts[r.id].district !== r.district
const missingDistrict = (r) => !r.district && districtsOf(r.region).length > 0

// 시·도를 바꿔서 기존 시·군이 새 목록에 없으면 비운다
function onRegionChange(r) {
  if (!districtsOf(drafts[r.id].region).includes(drafts[r.id].district)) drafts[r.id].district = ''
}

async function save(r) {
  delete rowErrors[r.id]
  message.value = ''
  try {
    const res = await updateRequesterRegion(r.id, drafts[r.id])
    Object.assign(r, res)
    const where = [res.region, res.district].filter(Boolean).join(' ')
    message.value = `${r.requester} → ${where}. 출장보고서 ${res.report_count}건에 함께 반영했습니다.`
  } catch (e) {
    rowErrors[r.id] = Object.values(e.data || {}).flat().join(' ') || e.message
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div v-if="error" class="alert alert-danger">{{ error }}</div>
    <div class="card mb-3"><div class="card-body">
      <h2 class="h6">요청처 지역 관리 <span v-if="data" class="text-muted fw-normal">· {{ data.results.length }}곳</span></h2>
      <p class="text-muted small">
        출장보고서를 업로드할 때 고른 시·도·시·군이 여기에 기억됩니다. 고치면 같은 요청처로 저장된 출장보고서의 지역도 함께 바뀝니다.
      </p>
      <div v-if="message" class="alert alert-success py-2">{{ message }}</div>
      <div v-if="data" class="table-responsive">
        <table class="table table-sm small align-middle mb-0">
          <thead>
            <tr>
              <th>요청처</th>
              <th class="text-end">보고서</th>
              <th style="min-width: 11rem">시·도</th>
              <th style="min-width: 9rem">시·군</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in data.results" :key="r.id" :class="{ 'table-warning': changed(r) }">
              <td>
                {{ r.requester }}
                <span v-if="missingDistrict(r)" class="badge bg-warning text-dark ms-1">시·군 미지정</span>
              </td>
              <td class="text-end">{{ r.report_count }}건</td>
              <td>
                <select v-model="drafts[r.id].region" class="form-select form-select-sm" :aria-label="`${r.requester} 시·도`"
                        @change="onRegionChange(r)">
                  <option v-for="name in data.regions" :key="name" :value="name">{{ name }}</option>
                </select>
              </td>
              <td>
                <select v-model="drafts[r.id].district" class="form-select form-select-sm" :aria-label="`${r.requester} 시·군`"
                        :disabled="!districtsOf(drafts[r.id].region).length">
                  <option value="">{{ districtsOf(drafts[r.id].region).length ? '선택' : '없음' }}</option>
                  <option v-for="name in districtsOf(drafts[r.id].region)" :key="name" :value="name">{{ name }}</option>
                </select>
              </td>
              <td class="text-nowrap">
                <button type="button" class="btn btn-primary btn-sm py-0" :disabled="!changed(r)" @click="save(r)">저장</button>
                <div v-if="rowErrors[r.id]" class="text-danger small">{{ rowErrors[r.id] }}</div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div></div>
  </div>
</template>
