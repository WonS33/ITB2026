# 시험용 엑셀 (가상 데이터)

조원 저장소(yeonk-rgb/newtork-dashboard)의 `src/modules/management/ledger/__fixtures__/` 에서 가져온 고객사 「경영지원_관리」 양식의 **가상 데이터** 파일이다. 거래처명은 모두 "(가상)".

- `ledger-sample.xlsx`: 정상 파일 (빨간 글씨 = 장기 미수금, H열 메모로 상태, 적요 날짜 10/15, 숫자 코드 118, 연두 배경 자동이체)
- `ledger-sample-issues.xlsx`: 문제가 섞인 파일 (외상매출금 상태 메모 없음, 코드만 있는 행, 0원 행, 외상매입금 총액 불일치)
