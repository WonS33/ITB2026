<script setup>
// 일련번호 조회: 4자리 또는 전체 번호로 검색 → (여러 건이면 목록에서 선택) → 11개 항목 표시
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getSerial, searchSerials } from '@/api/production'

const route = useRoute()
const query = ref('')
const results = ref(null) // 검색 결과 목록
const detail = ref(null) // 선택한 일련번호 상세
const error = ref('')
const busy = ref(false)

async function search() {
  error.value = ''
  detail.value = null
  results.value = null
  if (!query.value.trim()) return
  busy.value = true
  try {
    const data = await searchSerials(query.value)
    results.value = data.results
    if (data.results.length === 1) await select(data.results[0].serial_full)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function select(serialFull) {
  error.value = ''
  try {
    detail.value = await getSerial(serialFull)
  } catch (e) {
    error.value = e.message
  }
}

// 제조내역 목록에서 줄을 눌러 오면 ?q=일련번호 로 바로 검색해 상세를 연다
onMounted(() => {
  if (route.query.q) {
    query.value = String(route.query.q)
    search()
  }
})

const isObject = (v) => v !== null && typeof v === 'object'
</script>

<template>
  <div class="card mb-4">
    <div class="card-body">
      <h2 class="h6">일련번호 조회</h2>
      <form class="d-flex gap-2 mb-2" style="max-width: 420px" @submit.prevent="search">
        <input v-model="query" class="form-control form-control-sm" placeholder="4자리(예: 0001) 또는 전체 번호(예: N82260001)" aria-label="일련번호" />
        <button class="btn btn-primary btn-sm text-nowrap" :disabled="busy">검색</button>
      </form>
      <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>

      <p v-if="results && results.length === 0" class="text-muted small mb-0">검색 결과가 없습니다.</p>

      <!-- 여러 건이면 목록에서 고른다 -->
      <div v-if="results && results.length > 1" class="mb-3">
        <p class="small mb-1">{{ results.length }}건이 검색되었습니다. 조회할 번호를 고르세요.</p>
        <div class="list-group list-group-flush small" style="max-width: 640px">
          <button
            v-for="r in results"
            :key="r.serial_full"
            type="button"
            class="list-group-item list-group-item-action"
            :class="{ active: detail && detail.serial_full === r.serial_full }"
            @click="select(r.serial_full)"
          >
            <strong>{{ r.serial_full }}</strong> · {{ r.model_name || '-' }} · 제조 {{ r.manufactured_date || '-' }} · {{ r.customer || '-' }}
          </button>
        </div>
      </div>

      <div v-if="detail">
        <h3 class="h6 mt-2">{{ detail.serial_full }}</h3>
        <table class="table table-sm table-bordered small mb-1" style="max-width: 640px">
          <tbody>
            <tr v-for="item in detail.items" :key="item.no">
              <th class="table-light text-nowrap" style="width: 9rem">{{ item.no }}. {{ item.label }}</th>
              <td>
                <template v-if="isObject(item.value)">
                  <span v-for="(v, k) in item.value" :key="k" class="me-3 d-inline-block">
                    <span class="text-muted">{{ k }}</span> {{ v === null ? '(수주서 연결 후 표시)' : v || '-' }}
                  </span>
                </template>
                <template v-else>{{ item.value || '-' }}</template>
              </td>
            </tr>
          </tbody>
        </table>
        <p class="text-muted small mb-0">※ 플랜지(Flange)는 제조내역 엑셀에 없어 수주서 PDF로 보완합니다.</p>
      </div>
    </div>
  </div>
</template>
