# 08. REST API 목록 (제안)

> 이 문서 전체가 **(제안)**이다. 주소 규칙과 응답 형식은 1주차에 팀이 확정한다.
> 모든 요청·응답은 JSON이다(파일 업로드만 `multipart/form-data`). 모든 API는 로그인이 필요하다(로그인 API 제외).

## 공통

- 기본 주소: `/api/`
- 기간 조회 파라미터: `?year=2026&period=month|quarter|year&month=10&quarter=4`
- 권한이 없으면 `403`, 로그인하지 않았으면 `401`을 돌려준다.
- 권한 표기: **전체** = 대표·경영지원팀·관리자 / **생산 열람·수정**, **서비스 열람·수정** = 해당 팀 권한자 + 전체

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
| GET | `/api/production/due-calendar/?year=2026&month=10` | 당월 납기 캘린더 | 생산 열람 |

## 5. 서비스팀

| 메서드 | 주소 | 기능 | 권한 |
|---|---|---|---|
| GET | `/api/service/dashboard/` | 출장 횟수·월별 추이, 유상·무상 비율, 지역별, 부품·모델·담당자 순위 | 서비스 열람 |
| GET | `/api/service/reports/` | 출장보고서 목록 | 서비스 열람 |
| GET | `/api/service/reports/{id}/` | 출장보고서 상세(고장·작업 내용 포함) | 서비스 열람 |
| GET | `/api/service/part-prices/` | 부품별 단가 표 (단가 출처 확인 후) | 서비스 열람 |

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
