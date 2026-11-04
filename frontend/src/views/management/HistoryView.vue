<script setup>
// 변경 이력: 누가 언제 무엇을 바꿨는지 (최근 기록부터, 50건씩). 기록은 고치거나 지울 수 없다.
// 기록하는 일: 월간 입력 확정·확정 후 수정·확정 취소, 월간 입력 엑셀 다운로드 (임시저장은 기록하지 않음)
import { onMounted, reactive, ref, watch } from 'vue'
import { getHistory } from '@/api/management'
import ListPager from '@/components/ListPager.vue'

const PAGE_SIZE = 50
const filters = reactive({ from: '', to: '', actor: '', screen: '', action: '', q: '' })
const page = ref(1)
const data = ref(null)
const loading = ref(false)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await getHistory({ ...filters, page: page.value })
    // 기간을 비워 두면 서버 기본값(최근 30일)이 들어온다 → 칸에 보여 줌
    filters.from = data.value.from
    filters.to = data.value.to
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
function search() {
  page.value = 1
  load()
}
function reset() {
  Object.keys(filters).forEach((k) => (filters[k] = ''))
  search()
}
watch(page, load)
onMounted(load)
</script>

<template>
  <div>
    <form class="card mb-3" @submit.prevent="search">
      <div class="card-body row g-2 align-items-end">
        <div class="col-6 col-md-2">
          <label class="form-label small mb-1" for="h-from">시작일</label>
          <input id="h-from" v-model="filters.from" type="date" class="form-control form-control-sm" />
        </div>
        <div class="col-6 col-md-2">
          <label class="form-label small mb-1" for="h-to">종료일</label>
          <input id="h-to" v-model="filters.to" type="date" class="form-control form-control-sm" />
        </div>
        <div class="col-6 col-md-2">
          <label class="form-label small mb-1" for="h-actor">사람</label>
          <select id="h-actor" v-model="filters.actor" class="form-select form-select-sm">
            <option value="">전체</option>
            <option v-for="a in data?.actors ?? []" :key="a.id" :value="String(a.id)">{{ a.label }}</option>
          </select>
        </div>
        <div class="col-6 col-md-2">
          <label class="form-label small mb-1" for="h-screen">화면</label>
          <select id="h-screen" v-model="filters.screen" class="form-select form-select-sm">
            <option value="">전체</option>
            <option v-for="s in data?.screens ?? []" :key="s.key" :value="s.key">{{ s.label }}</option>
          </select>
        </div>
        <div class="col-6 col-md-2">
          <label class="form-label small mb-1" for="h-action">동작</label>
          <select id="h-action" v-model="filters.action" class="form-select form-select-sm">
            <option value="">전체</option>
            <option v-for="a in data?.actions ?? []" :key="a.key" :value="a.key">{{ a.label }}</option>
          </select>
        </div>
        <div class="col-6 col-md-2">
          <label class="form-label small mb-1" for="h-q">대상·아이디 검색</label>
          <input id="h-q" v-model="filters.q" type="search" class="form-control form-control-sm" placeholder="예: 10월" />
        </div>
        <div class="col-12 d-flex gap-2 justify-content-end">
          <button type="button" class="btn btn-sm btn-outline-secondary" @click="reset">초기화</button>
          <button type="submit" class="btn btn-sm btn-primary">조회</button>
        </div>
      </div>
    </form>

    <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
    <div v-if="loading && !data" class="text-muted">불러오는 중…</div>
    <div v-else-if="data" class="card">
      <div class="card-body">
        <p class="small text-muted mb-2">{{ data.total.toLocaleString() }}건 · 기록은 고치거나 지울 수 없습니다. 임시저장은 기록하지 않습니다.</p>
        <div class="table-responsive">
          <table class="table table-sm align-middle mb-0">
            <thead class="table-light">
              <tr><th>일시</th><th>사람</th><th>화면</th><th>동작</th><th>대상</th><th>바뀐 내용</th></tr>
            </thead>
            <tbody>
              <tr v-for="r in data.rows" :key="r.id">
                <td class="text-nowrap">{{ r.occurred_at }}</td>
                <td class="text-nowrap">{{ r.actor }}</td>
                <td class="text-nowrap">{{ r.screen }}</td>
                <td class="text-nowrap"><span class="badge badge-soft">{{ r.action }}</span></td>
                <td>{{ r.target }}</td>
                <td class="small">
                  <div v-for="(line, i) in r.lines" :key="i">{{ line }}</div>
                  <span v-if="!r.lines.length" class="text-muted">-</span>
                </td>
              </tr>
              <tr v-if="!data.rows.length"><td colspan="6" class="text-center text-muted py-4">조건에 맞는 기록이 없습니다.</td></tr>
            </tbody>
          </table>
        </div>
        <ListPager :page="data.page" :page-size="PAGE_SIZE" :total="data.total" @change="page = $event" />
      </div>
    </div>
  </div>
</template>
