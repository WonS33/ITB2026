// 팀 화면 왼쪽 메뉴 (위쪽 메뉴 줄에서 팀을 고르면, 왼쪽에는 그 팀의 하위 메뉴만 보인다)
// edit: true인 묶음은 그 팀 수정 권한자에게만 보인다. 실제 권한 확인은 라우터와 백엔드 API에서도 한다.
export const TEAM_MENUS = {
  production: [
    {
      group: '조회',
      items: [
        { label: '대시보드', to: '/production' },
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
      ],
    },
  ],
  service: [
    {
      group: '조회',
      items: [
        { label: '대시보드', to: '/service' },
        { label: '출장보고서 목록', to: '/service/reports' },
        { label: '교체부품 단가', to: '/service/part-prices' },
      ],
    },
    {
      group: '데이터 입력',
      edit: true,
      items: [
        { label: '출장보고서 업로드', to: '/service/upload' },
        { label: '부품 단가 입력', to: '/service/part-prices/input' },
        { label: '요청처 지역 관리', to: '/service/requester-regions' },
      ],
    },
  ],
}
