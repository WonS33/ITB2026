# 08. REST API 목록 (제안)

> 이 문서 전체가 **(제안)**이다. 주소 규칙과 응답 형식은 1주차에 팀이 확정한다.
> 모든 요청·응답은 JSON이다(파일 업로드만 `multipart/form-data`). 모든 API는 로그인이 필요하다(로그인 API 제외).

## 공통

- 기본 주소: `/api/`
- 기간 조회 파라미터: `?year=2026&period=month|quarter|year&month=10&quarter=4`
- 권한이 없으면 `403`, 로그인하지 않았으면 `401`을 돌려준다.
- 권한 표기: **전체** = 대표·관리자·경영지원팀 소속(팀장·팀원) / **생산 열람·수정**, **서비스 열람·수정** = 해당 팀 권한자 + 전체

## 1. 계정

| 메서드 | 주소 | 기능 | 권한 |
|---|---|---|---|
| POST | `/api/auth/login/` | 로그인 | 누구나 |
| POST | `/api/auth/logout/` | 로그아웃 | 로그인 사용자 |
| GET | `/api/auth/me/` | 내 정보·권한(`role`, `view_teams`, `edit_teams`, `must_change_password`) | 로그인 사용자 |
| POST | `/api/auth/password/` | 본인 비밀번호 변경 | 로그인 사용자 |

## 2. 관리자

| 메서드 | 주소 | 기능 | 권한 |
|---|---|---|---|
| GET | `/api/admin/users/` | 직원 목록 | 전체 |
| POST | `/api/admin/users/` | 계정 발급 | 전체 |
| PATCH | `/api/admin/users/{id}/` | 역할·열람 범위·수정 권한 변경 | 전체 |
| POST | `/api/admin/users/{id}/reset-password/` | 비밀번호 초기화 | 전체 |

## 3. 경영지원팀

| 메서드 | 주소 | 기능 | 권한 |
|---|---|---|---|
| GET / PUT | `/api/management/targets/{year}/` | 연간 목표매출 조회·입력 | 조회·입력: 전체 |
| GET / PUT | `/api/management/monthly/{year}/{month}/` | 월별 실적 조회·입력 | 조회·입력: 전체 |
| GET | `/api/management/dashboard/` | 메인 화면 집계(달성률, 매출 구성, 산업 분야·제품 비중, 매입·지출 추이, 미수금, 간이 지표) | 전체 |
| POST | `/api/management/ai-comment/` | AI 분석 코멘트 생성 (선택, 기업 허용 확인 후) | 전체 |

## 4. 생산팀

| 메서드 | 주소 | 기능 | 권한 |
|---|---|---|---|
| GET / PUT | `/api/production/targets/{year}/` | 연간 목표 생산량 | 조회: 생산 열람 / 입력: 생산 수정 |
| GET | `/api/production/dashboard/` | 생산량 달성률·부족치, 산업 분야·거래처·제품별 판매량 | 생산 열람 |
| GET | `/api/production/serials/?q=0001` | 일련번호 검색 (4자리·전체) | 생산 열람 |
| GET | `/api/production/serials/{serial_full}/` | 일련번호 11개 항목 상세 | 생산 열람 |
| GET | `/api/production/due-soon/` | 납기 임박: 출고가 끝나지 않은 수주 중 오늘부터 14일 안 + 납기 지남(최근 30일). 항목마다 `d_day`, `status`, `shipped`/`quantity` | 생산 열람 |
| GET | `/api/production/due-calendar/?year=2026&month=10` | 당월 납기 캘린더 | 생산 열람 |

## 5. 서비스팀

| 메서드 | 주소 | 기능 | 권한 |
|---|---|---|---|
| GET | `/api/service/dashboard/` | 출장 횟수·월별 추이, 유상·무상 비율, 지역별, 부품·모델·담당자 순위 | 서비스 열람 |
| GET | `/api/service/reports/` | 출장보고서 목록 | 서비스 열람 |
| POST | `/api/service/reports/` | 출장보고서 1건 직접 입력. 동행자·부품은 이름 목록, 제품은 `{model_name, spec, serial_no_raw, quantity}` 목록. 오류 400(칸별 메시지), 같은 시작일·요청처가 있으면 409 → `allow_duplicate: true`로 다시 보내면 저장 | 서비스 수정 |
| GET | `/api/service/reports/{id}/` | 출장보고서 상세(고장·작업 내용 포함) | 서비스 열람 |
| GET | `/api/service/part-prices/` | 부품별 현재·직전 단가, 증감, 이력, 단가 미등록 부품, 부품명 목록 | 서비스 열람 |
| POST | `/api/service/part-prices/` | 단가 한 줄 추가 (`part_name`, `unit_price`, `effective_date`) | 서비스 수정 |
| DELETE | `/api/service/part-prices/{id}/` | 잘못 입력한 단가 한 줄 삭제 | 서비스 수정 |
| (업로드) | `POST /api/uploads/` `kind=quote_pdf` | 유상 A/S 견적서 PDF → 부품 단가 (업로드 공통 흐름: 확인 → 저장) | 서비스 수정 |
| GET | `/api/service/requester-regions/` | 요청처 → 시·도·시·군 대응표 (보고서 수 포함), 시·도·시·군 목록 | 서비스 열람 |
| PATCH | `/api/service/requester-regions/{id}/` | 시·도·시·군 변경 → 같은 요청처의 저장된 출장보고서 지역도 함께 변경 | 서비스 수정 |

## 6. 업로드 (추출 → 확인 → 저장)

| 메서드 | 주소 | 기능 | 권한 |
|---|---|---|---|
| POST | `/api/uploads/` | 파일 업로드 + 추출 (`kind` 지정). 추출 결과와 누락·중복·형식 오류 목록을 돌려줌. DB에는 아직 저장하지 않음 | 해당 팀 수정 |
| PATCH | `/api/uploads/{id}/` | 확인 화면에서 수정한 추출 결과 반영 | 해당 팀 수정 |
| POST | `/api/uploads/{id}/confirm/` | 최종 저장 (기준 번호로 중복 제외) | 해당 팀 수정 |
| POST | `/api/uploads/{id}/cancel/` | 업로드 취소 | 해당 팀 수정 |

`kind`별 담당 팀: `manufacturing_excel`, `sales_order_pdf` → 생산 / `trip_report_pdf`, `trip_report_excel` → 서비스 / `history_excel` → 전체

## 변경 기록

- 2026-10-18: 지침(2026-10-17) 기준으로 최초 작성
- 2026-10-18: 계정 API 구현. 로그인 실패는 400. `GET /api/auth/me/`가 CSRF 쿠키도 내려준다. 미로그인 401은 `accounts.authentication.SessionAuthentication401`로 처리
- 2026-10-18: 업로드 API 4개 구현 (현재 `kind=manufacturing_excel`만 지원, 나머지는 400). 오류 행이 있을 때 confirm은 400과 최신 검사 결과(`batch`)를 돌려준다
- 2026-10-18: `POST /api/auth/password/` 구현 — 본문 `current_password`, `new_password`. 실패하면 400과 칸별 오류(한국어), 성공하면 내 정보(must_change_password=false)
- 2026-10-19: `GET /api/admin/users/`, `POST /api/admin/users/{id}/reset-password/` 구현. 초기화 응답은 `{user, temporary_password}`(Cache-Control: no-store), 본인 초기화는 400. 권한 없으면 403, 미로그인 401
- 2026-10-19: `PATCH /api/admin/users/{id}/` 구현 — 본문 `role`, `view_teams`, `edit_teams` 중 보낸 항목만 변경(그 외 항목은 무시). 수정 팀이 열람 팀에 없거나 본인을 팀장·팀원으로 바꾸면 400. 응답은 직원 한 줄(`view_teams`, `edit_teams`는 저장된 값)
- 2026-10-19: `role`에서 `management` 삭제, 팀 값에 `management` 추가. `GET /api/auth/me/`의 `view_teams`·`edit_teams`는 전체 권한자면 `["management","production","service"]`
- 2026-10-21: 서비스팀 부품 단가(조회·추가·삭제)와 요청처 지역 관리(조회·변경) API 구현
- 2026-10-21: `POST /api/service/reports/`(출장보고서 직접 입력) 구현. 목록·상세 응답에 `input_method` 추가
- 2026-10-26: 업로드 종류 `quote_pdf`(견적서 → 부품 단가) 추가. 확인 화면 열 정보에 `suggestions`(직접 입력하며 고르는 추천 목록) 추가. 부품 단가 응답에 출처(`current_source`, `history[].source`)와 견적 정보(`history[].company`·`project`·`note`) 추가
- 2026-10-27: `GET /api/production/due-soon/` 추가. 납기 캘린더 수주 묶음에 `shipped`(출고 대수), `status`(done/partial/pending), `overdue` 추가
