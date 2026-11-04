<script setup>
// 한 건의 변경 기록 (누가·언제·무엇을 바꿨는지, 최근부터)
import { onMounted, ref } from 'vue'
import { getRowHistory } from '@/api/management'

const props = defineProps({
  type: { type: String, required: true },
  id: { type: Number, required: true },
  label: { type: String, required: true },
})
const emit = defineEmits(['close'])
const rows = ref(null)
const error = ref('')

onMounted(async () => {
  try {
    rows.value = (await getRowHistory(props.type, props.id)).rows
  } catch (e) {
    error.value = e.message
  }
})
</script>

<template>
  <div class="modal d-block" tabindex="-1" role="dialog" aria-modal="true" aria-labelledby="row-history-title">
    <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable modal-lg">
      <div class="modal-content">
        <div class="modal-header">
          <h2 id="row-history-title" class="modal-title h5">변경 이력 · {{ label }}</h2>
          <button type="button" class="btn-close" aria-label="닫기" @click="emit('close')"></button>
        </div>
        <div class="modal-body">
          <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
          <p v-else-if="!rows" class="text-muted">불러오는 중…</p>
          <p v-else-if="!rows.length" class="text-muted mb-0">기록이 없습니다.</p>
          <table v-else class="table table-sm align-middle mb-0">
            <thead class="table-light"><tr><th>일시</th><th>사람</th><th>동작</th><th>바뀐 내용</th></tr></thead>
            <tbody>
              <tr v-for="r in rows" :key="r.id">
                <td class="text-nowrap">{{ r.occurred_at }}</td>
                <td class="text-nowrap">{{ r.actor }}</td>
                <td class="text-nowrap"><span class="badge badge-soft">{{ r.action }}</span></td>
                <td class="small"><div v-for="(line, i) in r.lines" :key="i">{{ line }}</div><span v-if="!r.lines.length" class="text-muted">-</span></td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="modal-footer"><button type="button" class="btn btn-outline-secondary" @click="emit('close')">닫기</button></div>
      </div>
    </div>
  </div>
  <div class="modal-backdrop show"></div>
</template>
