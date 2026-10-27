<script setup>
// 목록 아래 쪽 이동: "1–100 / 315건 [이전] [다음]"
import { computed } from 'vue'

const props = defineProps({
  page: { type: Number, required: true },
  pageSize: { type: Number, required: true },
  total: { type: Number, required: true },
})
const emit = defineEmits(['change'])

const lastPage = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))
const from = computed(() => (props.total ? (props.page - 1) * props.pageSize + 1 : 0))
const to = computed(() => Math.min(props.page * props.pageSize, props.total))
</script>

<template>
  <div v-if="lastPage > 1" class="d-flex align-items-center justify-content-end gap-2 small mt-2">
    <span class="text-muted">{{ from }}–{{ to }} / {{ total.toLocaleString() }}건</span>
    <button type="button" class="btn btn-outline-secondary btn-sm" :disabled="page <= 1" @click="emit('change', page - 1)">이전</button>
    <button type="button" class="btn btn-outline-secondary btn-sm" :disabled="page >= lastPage" @click="emit('change', page + 1)">다음</button>
  </div>
</template>
