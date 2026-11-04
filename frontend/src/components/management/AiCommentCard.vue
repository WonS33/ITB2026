<script setup>
// AI 분석 코멘트 카드 (조원 저장소 ai-comment-card·ai-comment-panel 을 옮김) — 메인 대시보드·경영지원 상세 맨 위 공용
// 화면을 열 때는 저장된 코멘트만 읽는다. [분석하기]/[다시 분석]을 눌러야 백엔드가 외부 AI 를 부른다
// 제목·생성 정보·버튼 → 굵은 한 줄(연간 목표, 서버 계산) → 3단(이번 기간 현황 / 부족한 점·주의 / 다음 분기 개선할 점)
import { ref, watch } from 'vue'
import { generateAiComment, getAiComment } from '@/api/management'
import { period } from '@/period'

const view = ref(null)
const loadError = ref('')
const pending = ref(false)
const failure = ref(null) // { message, retryable }
const done = ref('')

async function load() {
  loadError.value = ''
  try {
    view.value = await getAiComment(period)
  } catch (e) {
    loadError.value = e.message
  }
}
watch(period, () => { failure.value = null; done.value = ''; load() }, { deep: true, immediate: true })

const dateTime = (iso) => new Date(iso).toLocaleString('sv-SE').slice(0, 19) // 2026-11-04 14:13:35

async function generate() {
  const v = view.value
  // 관리자(대표)가 허락 전 실제 숫자를 외부 AI 로 보내는 경우 — 한 번 확인
  if (v.abilities.consent_notice && !window.confirm(v.abilities.consent_notice)) return
  failure.value = null
  done.value = ''
  pending.value = true
  try {
    const res = await generateAiComment({ year: v.year, quarter: v.quarter, expected_latest_id: v.latest_id, consent: !!v.abilities.consent_notice })
    await load()
    done.value = res.message
  } catch (e) {
    failure.value = { message: e.message, retryable: e.status === 502 && e.data?.retryable }
    if (e.status === 409) await load()
  } finally {
    pending.value = false
  }
}

const COLUMNS = [
  { key: 'summary', title: '이번 기간 현황', dot: 'var(--bs-gray-700)' },
  { key: 'shortfalls', title: '부족한 점·주의', dot: 'var(--bs-danger)' },
  { key: 'improvements', title: '다음 분기 개선할 점', dot: 'var(--brand)' },
]
</script>

<template>
  <section class="card ai-card mb-4" aria-label="AI 분석 코멘트">
    <div class="card-body">
      <div class="d-flex flex-wrap align-items-start gap-2 mb-2">
        <h2 class="h6 mb-0">AI 분석 코멘트<template v-if="view?.quarter"> · {{ view.quarter_label }}</template></h2>
        <div class="ms-auto d-flex flex-wrap align-items-center gap-2">
          <span v-if="view?.latest" class="small text-muted">{{ view.latest.method_label }} · {{ dateTime(view.latest.created_at) }}<template v-if="view.latest.created_by"> · {{ view.latest.created_by }}</template></span>
          <button v-if="view?.abilities?.can_generate" type="button" class="btn btn-sm btn-primary" :disabled="pending" @click="generate">
            <span v-if="pending" class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>
            {{ pending ? '분석 중…' : view.latest ? '다시 분석' : '분석하기' }}
          </button>
        </div>
      </div>

      <div v-if="loadError" class="alert alert-danger py-2 small mb-0">{{ loadError }}</div>
      <p v-else-if="!view" class="small text-muted mb-0">불러오는 중…</p>
      <p v-else-if="!view.quarter" class="small text-muted text-center py-3 mb-0">{{ view.notice }}</p>
      <template v-else>
        <p v-if="view.basis_note" class="small text-muted mb-2">{{ view.basis_note }}</p>
        <p v-if="view.stale_reason && !pending" class="small text-warn bg-warn-soft rounded px-3 py-2 mb-2">
          {{ view.stale_reason === 'prompt' ? '분석 기준이 바뀌어 이전 기준으로 만든 분석입니다.' : '데이터가 변경되어 분석이 최신이 아닙니다.' }}
          {{ view.abilities.can_generate ? '[다시 분석]을 누르면 지금 데이터로 다시 분석합니다.' : '경영지원팀이 다시 분석하면 갱신됩니다.' }}
        </p>
        <p v-if="pending" role="status" class="small bg-light rounded px-3 py-2 mb-2">AI가 분석 중입니다. 1분 정도 걸릴 수 있습니다.</p>
        <div v-if="failure && !pending" role="alert" class="alert alert-danger py-2 small mb-2">
          {{ failure.message }}
          <button v-if="failure.retryable" type="button" class="btn btn-link btn-sm p-0 ms-2 align-baseline" @click="generate">다시 시도</button>
        </div>
        <p v-if="done && !pending" role="status" class="small text-muted mb-2">{{ done }}</p>

        <div v-if="view.latest" :class="{ 'opacity-50': pending }">
          <p v-if="view.latest.result.headline" class="fw-semibold mb-3">{{ view.latest.result.headline }}</p>
          <div class="row g-3 small">
            <div v-for="c in COLUMNS" :key="c.key" class="col-md-4">
              <h3 class="h6 small fw-semibold d-flex align-items-center gap-2 mb-2"><span class="dot" :style="{ background: c.dot }"></span>{{ c.title }}</h3>
              <ul class="mb-0 ps-3">
                <li v-for="(t, i) in view.latest.result[c.key]" :key="i" class="mb-1">{{ t }}</li>
                <li v-if="!view.latest.result[c.key].length && !(c.key === 'improvements' && view.latest.result.long_overdue?.length)" class="text-muted list-unstyled">없음</li>
                <!-- 장기 미수금 거래처명: AI 로 보내지 않고 서버가 붙인 것 -->
                <li v-if="c.key === 'improvements' && view.latest.result.long_overdue?.length" class="text-muted">
                  장기 미수금 거래처: {{ view.latest.result.long_overdue.map((x) => `${x.name}(${x.amount})`).join(', ') }}
                </li>
              </ul>
            </div>
          </div>
        </div>
        <p v-else-if="!pending" class="small text-muted text-center py-3 mb-0">
          {{ view.abilities.notice ?? (view.abilities.can_generate ? '[분석하기]를 누르면 이 분기의 현황·부족한 점·개선할 점을 정리합니다.' : '아직 분석이 없습니다.') }}
        </p>
        <p v-if="view.latest && view.abilities.notice" class="small text-muted mt-2 mb-0">{{ view.abilities.notice }}</p>

        <p class="small text-muted border-top pt-2 mt-3 mb-0">
          {{ view.latest?.method === 'example' ? '가상 데이터로 만든 예시 분석입니다. [다시 분석]을 누르면 새 분석으로 바뀝니다.' : view.latest?.method === 'mock' ? '개발용 모의 응답입니다 (실제 AI 분석 아님).' : 'AI가 생성한 참고용 요약입니다. 계산된 숫자만 근거로 하며, 판단은 담당자가 확인하세요.' }}
        </p>
      </template>
    </div>
  </section>
</template>

<style scoped>
.ai-card { border-left: 4px solid var(--brand); }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; }
.bg-warn-soft { background: #fff3cd; }
</style>
