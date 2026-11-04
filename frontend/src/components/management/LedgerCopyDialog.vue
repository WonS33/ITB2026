<script setup>
// [지난달 내용 불러오기] 미리보기 → 저장 (조원 저장소 copy-previous-dialog 를 옮김)
// 엑셀처럼 지난달 내역을 복사해서 잔액만 고치는 방식. 이번 달이 비어 있을 때만 (중복 방지)
// 당월 수금 행은 지난달에 이미 받은 돈이라 기본 제외 — 포함하면 "당월 수금예정"으로 바꾼다. 완료일은 모두 비운다
import { computed, onMounted, ref } from 'vue'
import { copyLedger, previewLedgerCopy } from '@/api/management'
import { won } from '@/money'

const props = defineProps({
  year: { type: Number, required: true },
  month: { type: Number, required: true },
  kindLabels: { type: Object, required: true },
})
const emit = defineEmits(['done', 'close'])
const preview = ref(null)
const error = ref('')
const saving = ref(false)
const includeCollected = ref(false)
const monthText = `${props.year}-${String(props.month).padStart(2, '0')}`

onMounted(async () => {
  try {
    preview.value = await previewLedgerCopy(props.year, props.month)
  } catch (e) {
    error.value = e.message
  }
})

// 미리보기 금액은 당월 수금 제외 기준 — 포함하면 외상매출금에 더한다
const kinds = computed(() =>
  preview.value.kinds.map((k) =>
    k.kind === 'ar' && includeCollected.value
      ? { ...k, count: k.count + preview.value.collected.count, amount: k.amount + preview.value.collected.amount }
      : k,
  ),
)
const total = computed(() => kinds.value.reduce((s, k) => s + k.count, 0))

async function save() {
  saving.value = true
  error.value = ''
  try {
    const res = await copyLedger({
      year: props.year,
      month: props.month,
      include_collected: includeCollected.value,
      expected_source_count: preview.value.source_count,
    })
    emit('done', res.message)
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="modal d-block" tabindex="-1" role="dialog" aria-modal="true" aria-labelledby="ledger-copy-title">
    <div class="modal-dialog modal-dialog-centered">
      <div class="modal-content">
        <div class="modal-header">
          <h2 id="ledger-copy-title" class="modal-title h5">지난달 내용 불러오기 → {{ monthText }}</h2>
          <button type="button" class="btn-close" aria-label="닫기" @click="emit('close')"></button>
        </div>
        <div class="modal-body">
          <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
          <p v-if="!preview && !error" class="text-muted">불러오는 중…</p>
          <template v-else-if="preview">
            <p v-if="preview.existing" class="alert alert-warning py-2 mb-0">
              {{ monthText }}에 이미 {{ preview.existing }}행이 있어 불러올 수 없습니다. 지난달 내용은 이번 달이 비어 있을 때만 불러옵니다.
            </p>
            <p v-else-if="!preview.source_count" class="mb-0">{{ preview.from }}에 입력된 행이 없습니다.</p>
            <template v-else>
              <p class="small text-muted">
                {{ preview.from }} 내용을 그대로 복사합니다. 거래처·적요·예정일·거래처코드·자동이체는 그대로, 완료일은 비웁니다.
                불러온 뒤 잔액을 이번 달 값으로 고치세요.
              </p>
              <table class="table table-sm mb-2">
                <thead class="table-light"><tr><th>구분</th><th class="text-end">행</th><th class="text-end">잔액 합계</th></tr></thead>
                <tbody>
                  <tr v-for="k in kinds" :key="k.kind"><td>{{ kindLabels[k.kind] }}</td><td class="text-end">{{ k.count }}</td><td class="text-end">{{ won(k.amount) }}</td></tr>
                </tbody>
              </table>
              <label v-if="preview.collected.count" class="form-check small">
                <input v-model="includeCollected" type="checkbox" class="form-check-input" />
                지난달 "당월 수금" {{ preview.collected.count }}행({{ won(preview.collected.amount) }})도 포함 — "당월 수금예정"으로 바꿔 넣습니다
              </label>
              <p v-if="preview.collected.count && !includeCollected" class="small text-muted mb-0">당월 수금 행은 지난달에 이미 받은 돈이라 기본으로 빼 둡니다.</p>
            </template>
          </template>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-outline-secondary" @click="emit('close')">닫기</button>
          <button v-if="preview && !preview.existing && preview.source_count" type="button" class="btn btn-primary" :disabled="saving || !total" @click="save">
            {{ saving ? '불러오는 중…' : `${total}행 불러오기` }}
          </button>
        </div>
      </div>
    </div>
  </div>
  <div class="modal-backdrop show"></div>
</template>
