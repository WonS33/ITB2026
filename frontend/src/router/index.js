import { createRouter, createWebHistory } from 'vue-router'
import { auth, canEdit, canView, homePath, loadMe } from '@/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
    { path: '/', redirect: () => homePath() },
    // meta.team: 이 화면을 보려면 해당 팀 열람 권한이 필요하다
    // 팀 화면: 왼쪽 메뉴 틀(TeamLayout) 안에 하위 화면. meta.edit: 그 팀 수정 권한이 필요한 화면
    {
      path: '/production',
      component: () => import('@/components/TeamLayout.vue'),
      meta: { team: 'production' },
      children: [
        { path: '', component: () => import('@/views/production/DashboardView.vue') },
        { path: 'serials', component: () => import('@/views/production/SerialsView.vue') },
        { path: 'calendar', component: () => import('@/views/production/CalendarView.vue') },
        { path: 'upload/manufacturing', component: () => import('@/views/production/ManufacturingUploadView.vue'), meta: { edit: true } },
        { path: 'upload/orders', component: () => import('@/views/production/OrderUploadView.vue'), meta: { edit: true } },
      ],
    },
    {
      path: '/service',
      component: () => import('@/components/TeamLayout.vue'),
      meta: { team: 'service' },
      children: [
        { path: '', component: () => import('@/views/service/DashboardView.vue') },
        { path: 'reports', component: () => import('@/views/service/ReportsView.vue') },
        { path: 'part-prices', component: () => import('@/views/service/PartPricesView.vue') },
        { path: 'upload', component: () => import('@/views/service/TripUploadView.vue'), meta: { edit: true } },
        { path: 'part-prices/input', component: () => import('@/views/service/PartPriceInputView.vue'), meta: { edit: true } },
        { path: 'requester-regions', component: () => import('@/views/service/RequesterRegionsView.vue'), meta: { edit: true } },
      ],
    },
    { path: '/password', component: () => import('@/views/PasswordView.vue') },
    // meta.fullAccess: 대표·경영지원팀·관리자만
    { path: '/admin', component: () => import('@/views/AdminView.vue'), meta: { fullAccess: true } },
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
  if (to.meta.edit && !canEdit(to.meta.team)) return '/forbidden'
  if (to.meta.fullAccess && !auth.user.has_full_access) return '/forbidden'
  return true
})

export default router
