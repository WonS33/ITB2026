import { createRouter, createWebHistory } from 'vue-router'
import { auth, canView, homePath, loadMe } from '@/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
    { path: '/', redirect: () => homePath() },
    // meta.team: 이 화면을 보려면 해당 팀 열람 권한이 필요하다
    { path: '/production', component: () => import('@/views/ProductionView.vue'), meta: { team: 'production' } },
    { path: '/service', component: () => import('@/views/ServiceView.vue'), meta: { team: 'service' } },
    { path: '/forbidden', component: () => import('@/views/ForbiddenView.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

// 화면을 옮길 때마다 로그인·열람 권한을 확인한다
router.beforeEach(async (to) => {
  if (!auth.loaded) await loadMe()

  if (to.meta.public) {
    return auth.user && to.path === '/login' ? homePath() : true
  }
  if (!auth.user) return { path: '/login', query: { next: to.fullPath } }
  if (to.meta.team && !canView(to.meta.team)) return '/forbidden'
  return true
})

export default router
