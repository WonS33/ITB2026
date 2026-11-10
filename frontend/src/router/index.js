import { createRouter, createWebHistory } from 'vue-router'
import { auth, canEdit, canView, homePath, loadMe } from '@/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
    // 첫 화면: 아래 beforeEach에서 내 정보를 받은 뒤 볼 수 있는 첫 팀 화면으로 보낸다 (화면 자체는 없음).
    // redirect를 쓰면 내 정보를 받기 전에 실행돼 "권한 없음" 화면으로 잘못 가므로 쓰지 않는다
    { path: '/', component: { render: () => null }, meta: { home: true } },
    // meta.team: 이 화면을 보려면 해당 팀 열람 권한이 필요하다
    // 팀 화면: 왼쪽 메뉴 틀(TeamLayout) 안에 하위 화면. meta.edit: 그 팀 수정 권한이 필요한 화면
    // 경영지원팀 (조원 저장소 yeonk-rgb/newtork-dashboard 기능을 옮김)
    {
      path: '/management',
      component: () => import('@/components/TeamLayout.vue'),
      meta: { team: 'management' },
      children: [
        { path: '', component: () => import('@/views/management/DashboardView.vue') },
        { path: 'entry', component: () => import('@/views/management/EntryView.vue'), meta: { edit: true } },
        { path: 'detail', component: () => import('@/views/management/DetailView.vue') },
        { path: 'history', component: () => import('@/views/management/HistoryView.vue') },
        { path: 'settings', component: () => import('@/views/management/SettingsView.vue'), meta: { edit: true } },
        { path: 'ledger', component: () => import('@/views/management/LedgerView.vue'), meta: { edit: true } },
        { path: 'ledger/import', component: () => import('@/views/management/LedgerImportView.vue'), meta: { edit: true, title: '경영지원 관리 엑셀 이관' } },
        { path: 'receivables', component: () => import('@/views/management/ReceivablesView.vue'), meta: { edit: true } },
      ],
    },
    {
      path: '/production',
      component: () => import('@/components/TeamLayout.vue'),
      meta: { team: 'production' },
      children: [
        { path: '', component: () => import('@/views/production/DashboardView.vue') },
        { path: 'records', component: () => import('@/views/production/RecordsView.vue') },
        { path: 'orders', component: () => import('@/views/production/OrdersView.vue') },
        { path: 'serials', component: () => import('@/views/production/SerialsView.vue') },
        { path: 'calendar', component: () => import('@/views/production/CalendarView.vue') },
        { path: 'upload/manufacturing', component: () => import('@/views/production/ManufacturingUploadView.vue'), meta: { edit: true } },
        { path: 'upload/orders', component: () => import('@/views/production/OrderUploadView.vue'), meta: { edit: true } },
        { path: 'uploads', component: () => import('@/views/UploadHistoryView.vue'), meta: { edit: true } },
      ],
    },
    {
      path: '/service',
      component: () => import('@/components/TeamLayout.vue'),
      meta: { team: 'service' },
      children: [
        { path: '', component: () => import('@/views/service/DashboardView.vue') },
        { path: 'reports', component: () => import('@/views/service/ReportsView.vue') },
        // meta.section 'prices': 왼쪽 메뉴의 '단가' 구역 화면 (권한은 서비스팀 그대로)
        { path: 'part-prices', component: () => import('@/views/service/PartPricesView.vue'), meta: { section: 'prices', title: '부품 단가' } },
        { path: 'upload', component: () => import('@/views/service/TripUploadView.vue'), meta: { edit: true } },
        { path: 'reports/new', component: () => import('@/views/service/TripReportFormView.vue'), meta: { edit: true } },
        { path: 'part-prices/input', component: () => import('@/views/service/PartPriceInputView.vue'), meta: { edit: true, section: 'prices', title: '단가 직접 입력' } },
        { path: 'upload/quotes', component: () => import('@/views/service/QuoteUploadView.vue'), meta: { edit: true, section: 'prices', title: '견적서 업로드' } },
        { path: 'requester-regions', component: () => import('@/views/service/RequesterRegionsView.vue'), meta: { edit: true } },
        { path: 'uploads', component: () => import('@/views/UploadHistoryView.vue'), meta: { edit: true } },
      ],
    },
    { path: '/password', component: () => import('@/views/PasswordView.vue') },
    // meta.fullAccess: 대표·관리자·경영지원팀 소속만
    { path: '/admin', component: () => import('@/views/AdminView.vue'), meta: { fullAccess: true } },
    // 제품 단가·원가 (원가·마진·커미션 = 대외비, 2026-11-02)
    { path: '/pricing', component: () => import('@/views/PricingView.vue'), meta: { fullAccess: true } },
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
  if (to.meta.home) return homePath()
  if (to.meta.team && !canView(to.meta.team)) return '/forbidden'
  if (to.meta.edit && !canEdit(to.meta.team)) return '/forbidden'
  if (to.meta.fullAccess && !auth.user.has_full_access) return '/forbidden'
  return true
})

export default router
