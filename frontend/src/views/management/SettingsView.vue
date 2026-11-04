<script setup>
// 목표·항목 설정: 탭 2개 (연간 목표 / 그 외 지출 항목). 저장하면 변경 이력에 남는다
// 탭을 바꿔도 입력 중인 값이 사라지지 않게 두 탭을 모두 두고 보이기만 바꾼다
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import CategoryManager from '@/components/management/CategoryManager.vue'
import TargetForm from '@/components/management/TargetForm.vue'

const TABS = [
  { key: 'target', label: '연간 목표' },
  { key: 'categories', label: '그 외 지출 항목' },
]
const route = useRoute()
const router = useRouter()
const tab = ref(route.query.tab === 'categories' ? 'categories' : 'target')

function select(key) {
  tab.value = key
  router.replace({ query: key === 'target' ? {} : { tab: key } }) // 새로고침해도 같은 탭
}
</script>

<template>
  <div>
    <p class="small text-muted mb-2">저장한 내용은 [변경 이력]에 누가·언제·무엇을 바꿨는지 남습니다.</p>
    <ul class="nav nav-tabs mb-3" role="tablist">
      <li v-for="t in TABS" :key="t.key" class="nav-item" role="presentation">
        <button type="button" class="nav-link" :class="{ active: tab === t.key }" role="tab" :aria-selected="tab === t.key" @click="select(t.key)">
          {{ t.label }}
        </button>
      </li>
    </ul>
    <TargetForm v-show="tab === 'target'" />
    <CategoryManager v-show="tab === 'categories'" />
  </div>
</template>
