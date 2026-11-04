// 팀 화면 왼쪽 메뉴 (위쪽 메뉴 줄에서 팀을 고르면, 왼쪽에는 그 팀의 하위 메뉴만 보인다)
// edit: true인 묶음은 그 팀 수정 권한자에게만 보인다. 실제 권한 확인은 라우터와 백엔드 API에서도 한다.
export const TEAM_MENUS = {
  management: [
    { group: '조회', items: [{ label: '대시보드', to: '/management' }, { label: '변경 이력', to: '/management/history' }] },
    {
      group: '데이터 입력',
      edit: true,
      items: [
        { label: '월간 입력', to: '/management/entry' },
        { label: '경영지원 관리', to: '/management/ledger' },
        { label: '목표·항목 설정', to: '/management/settings' },
        { label: '미수금 건별 기록', to: '/management/receivables' },
      ],
    },
  ],
  production: [
    {
      group: '조회',
      items: [
        { label: '대시보드', to: '/production' },
        { label: '제조내역', to: '/production/records' },
        { label: '수주 내역', to: '/production/orders' },
        { label: '일련번호 조회', to: '/production/serials' },
        { label: '납기 캘린더', to: '/production/calendar' },
      ],
    },
    {
      group: '데이터 입력',
      edit: true,
      items: [
        { label: '제조내역 업로드', to: '/production/upload/manufacturing' },
        { label: '수주서 업로드', to: '/production/upload/orders' },
        { label: '업로드 이력', to: '/production/uploads' },
      ],
    },
  ],
  service: [
    {
      group: '조회',
      items: [
        { label: '대시보드', to: '/service' },
        { label: '출장보고서 목록', to: '/service/reports' },
      ],
    },
    {
      group: '데이터 입력',
      edit: true,
      items: [
        { label: '출장보고서 업로드', to: '/service/upload' },
        { label: '출장보고서 직접 입력', to: '/service/reports/new' },
        { label: '요청처 지역 관리', to: '/service/requester-regions' },
        { label: '업로드 이력', to: '/service/uploads' },
      ],
    },
  ],
}

// 왼쪽 메뉴 '단가' 구역 (2026-11-02 사용자 요청: 부품 단가와 제품 단가·원가를 팀 메뉴와 따로 눈에 띄게)
// 부품 단가 화면은 주소·권한이 서비스팀 그대로(서비스팀 열람 권한), 제품 단가·원가는 대표·관리자·경영지원팀만
// view: 같은 화면의 탭(?view=) — 메뉴에서 바로 그 탭으로 간다
export const PRICE_MENU = [
  { label: '부품별 비교', path: '/service/part-prices', view: '' },
  { label: '출장지별 비교', path: '/service/part-prices', view: 'companies' },
  // 단가 넣기: 견적서 PDF 업로드 / 직접 입력 (출장보고서 메뉴처럼 짝으로, 2026-11-02)
  { label: '견적서 업로드', path: '/service/upload/quotes', view: '', edit: true },
  { label: '단가 직접 입력', path: '/service/part-prices/input', view: '', edit: true },
]
