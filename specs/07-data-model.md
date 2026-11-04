# 07. 데이터 모델 (제안)

> 이 문서 전체가 **(제안)**이다. 1주차에 팀이 합의해 확정한다. 기업 답변([11](11-open-questions.md))에 따라 필드가 바뀔 수 있다.
> 지침 7장에 따라 1주차 설계에는 추가 구현 지표(원가·매입·수주 등)에 필요한 항목도 고려하되, 실제 테이블은 지표 정의가 확인된 뒤 만든다.

## 공통 규칙

- 금액: 원 단위 정수 (`BigIntegerField` 등)
- 날짜: `DateField` (YYYY-MM-DD)
- 지역: 시·도 이름 문자열
- 월 단위 데이터는 `year`, `month`로 저장하고 분기·연간은 조회할 때 합산한다.
- 모든 테이블에 `created_at`, `updated_at`, 입력자(`created_by`)를 둔다.

## 1. 사용자

### User (`AbstractUser` 상속) — 확정: AbstractUser 확장

| 필드 | 설명 |
|---|---|
| (기본) `username`, `password`, `first_name`, `last_name`, `last_login`, `is_active` 등 | AbstractUser 기본 필드 |
| `role` | `ceo` / `admin` / `leader` / `member` (2026-10-19 `management` → 팀으로 이동) |
| `view_teams` | 열람 가능한 팀 목록 = 소속 팀 (`management`, `production`, `service`). `management` 소속이면 전체 권한 |
| `edit_teams` | 수정 가능한 팀 목록 (`production`, `service`) |
| `must_change_password` | 첫 로그인 비밀번호 변경 안내 여부 |

자세한 규칙은 [02-users-permissions.md](02-users-permissions.md).

## 2. 경영지원팀

### AnnualSalesTarget — 연간 목표매출 (구현 2026-11-04)

| 필드 | 설명 |
|---|---|
| `year` (unique) | 연도 |
| `target_amount` | 연간 목표매출액(원, 0원 초과) |
| `q1_target` ~ `q4_target` | 분기 목표 (선택, 비우면 null = 자동 배분: (연간 − 입력한 분기 합) ÷ 빈 분기 수, 나머지 원은 마지막 빈 분기에) |
| `headcount` | 직원 수 (선택, 인당 생산성용) |
| `updated_by` | 마지막 수정자 |

### MonthlyFinance — 월별 실적 (구현: `backend/management/models.py`, 2026-11-04)

조원 저장소(yeonk-rgb/newtork-dashboard)의 `management.prisma`를 옮김. 임시저장·확정 두 상태가 있고 **대시보드에는 확정된 달만** 반영한다.

| 필드 | 설명 |
|---|---|
| `year`, `month` (함께 unique) | 연월 |
| `product_sales` | 제품 매출액 |
| `merchandise_sales` | 상품 매출액 |
| `service_sales` | 용역 매출액 |
| `merchandise_purchase` | 상품 매입액 |
| `material_purchase` | 원재료 매입액 |
| `expense` | 경비 지출액 |
| `cash_balance` | 월말 통장 잔액 (선택, 비우면 null — 0원과 다름. 합계에 넣지 않음) |
| `status` | `draft`(임시저장) / `confirmed`(확정) |
| `confirmed_at`, `updated_by` | 확정 일시, 마지막 수정자 |

### ExpenseCategory — "그 외 지출" 항목

| 필드 | 설명 |
|---|---|
| `name` (unique) | 항목 이름 (예: 광고선전비, 접대비) |
| `cost_type` | `fixed`(고정비) / `variable`(변동비) / 빈 값(미분류) |
| `is_active` | False면 새 입력 화면에서 숨김 (과거 금액은 유지) |
| `sort_order` | 화면 순서 |
| `updated_at` | 수정 시각 (항목 목록 동시 수정 확인용) |

### OtherExpense — 월별 "그 외 지출" 금액

| 필드 | 설명 |
|---|---|
| `monthly` → MonthlyFinance, `category` → ExpenseCategory (함께 unique) | 어느 달의 어느 항목 |
| `amount` | 금액 |

### LedgerEntry — 경영지원 관리 장부 (2026-11-04)

고객사 「경영지원_관리」 엑셀의 블록 4개(외상매출금·외상매입금·미지급비용-직원·미지급비용-업체)를 기준년월·거래처별로 저장. 금액은 부가세 포함.

| 필드 | 설명 |
|---|---|
| `year`, `month`, `kind` | 기준년월, 구분 (`ar`·`ap`·`accrued_staff`·`accrued_vendor`) |
| `ar_status` / `purchase_type` / `expense_type`, `auto_transfer` | 구분마다 쓰는 칸 (외상매출금 상태, 외상매입금 매입유형, 업체 비용유형·자동이체) |
| `partner_code`, `partner_name`, `amount`, `note` | 거래처코드(외상매출금), 거래처명, 잔액, 적요 |
| `due_on`, `settled_on`, `deleted_at`, `deleted_by`, `updated_by` | 예정일, 완료일(외상매출금은 당월 수금일 때만·필수), 숨긴 일시·사람(삭제 대신), 마지막 수정자 |

- 화면: 경영지원 관리(`/management/ledger`). 외상매출금 장기 미수금 + 당월 수금예정 = 대시보드 미수금, 나머지 세 구분은 월간 입력 [불러오기]의 원본

### AuditLog — 변경 기록 (2026-11-04)

| 필드 | 설명 |
|---|---|
| `occurred_at`, `actor`, `actor_username` | 언제, 누가 (사용자를 지워도 남도록 그때 아이디도 저장) |
| `screen`, `action` | 어느 화면(`entry`·`entry-export`), 무엇을(`CONFIRM`·`UPDATE_CONFIRMED`·`UNCONFIRM`·`EXPORT`) |
| `target_type`, `target_id`, `target_label` | 대상 (예: "2026년 10월 월간 입력") |
| `changes`, `meta` | 바뀐 칸 [{field, label, before, after}] (화면 표기 그대로), 추가 정보(다운로드 기간·파일 이름) |

- 한 번 넣은 기록은 고치거나 지울 수 없다(모델 `save`·`delete`에서 막음, 관리 화면도 보기만). 비밀번호·토큰 같은 칸 이름은 기록하지 않는다.

### Receivable — 미수금 건별 기록 (2026-11-04)

| 필드 | 설명 |
|---|---|
| `customer_name`, `occurred_on`, `amount` | 거래처, 발생일, 금액 |
| `due_on` | 수금 예정일 (선택) |
| `is_collected`, `collected_on` | 수금 완료 여부, 수금일 |
| `note` | 비고 |
| `deleted_at`, `deleted_by` | 숨김(삭제 대신) — 목록·통계에서 빠지고 복구 가능 |

- 건별 메모·수금 기록용. 대시보드 미수금은 LedgerEntry 외상매출금 기준(조원 저장소 2026-10-26 결정)

- 처음 설계의 `other_expense`(합계 1개)는 항목별 표(ExpenseCategory·OtherExpense)로, `receivables`(월 합계)는 Receivable(건별)·LedgerEntry 외상매출금(대시보드)으로 나눴다.

### AiComment — AI 분석 코멘트 (2026-11-04)

| 필드 | 설명 |
|---|---|
| year, quarter | 분석한 분기 (분기마다 여러 개, 가장 최근 것을 보여 줌) |
| input_summary | 외부 AI로 보낸 합계 숫자 그대로 (거래처명·건별 내역 없음) |
| result | summary·shortfalls·improvements(각 3문장까지) + 서버가 붙인 headline·long_overdue(거래처명) |
| input_hash | 입력의 SHA-256 — 지금 데이터와 다르면 "최신이 아님" |
| model | 실제 모델 이름 / `mock`(모의 응답) / `example`(예시) |
| prompt_version, created_by, created_at | 분석 기준 버전·생성한 사람·일시 |

## 3. 생산팀

### AnnualProductionTarget — 연간 목표 생산량

| 필드 | 설명 |
|---|---|
| `year` (unique) | 연도 |
| `target_quantity` | 연간 목표 생산량(대) |

### ManufacturingRecord — 제조내역 (엑셀 1행 = 1대)

| 필드 | 엑셀 열 | 설명 |
|---|---|---|
| `serial_full` (unique) | — | 전체 일련번호 (타입 문자+국가 2자리+년도 2자리+4자리) |
| `serial_short` | 일련번호 | 4자리 (검색용, index) |
| `model_name` | 모델명 | 전체 모델명 (예: NTI-04). 셀 값 `04` + 표시 형식 `"NTI-"`를 합쳐 저장 |
| `bush_machining` | 부시 가공 | 6자리 숫자 |
| `rpm` | rpm | 빈칸 가능 |
| `power` | 전원 | 빈칸 가능 |
| `manufactured_date` | 제조년월 | 일 단위 날짜 (월간 생산량 집계 기준) |
| `inspection_date` | 검사일자 | |
| `inspection_no` | 검사번호 | 전체 번호(NTK + 년도 2자리 + 3자리)로 저장 |
| `po_no` | 뉴토크 번호 PO번호 | 예: 26006 |
| `so_no` | SO번호 | 빈칸 가능 |
| `customer_order_no` | 거래처 주문번호 | 샘플 엑셀 L열 (2026-10-18 추가) |
| `customer` | 거래처 | 판매처 |
| `final_orderer` | 최종발주처 | |
| `project_name` | 사업명 | |
| `shipped_date` | 출고일 | |
| `due_date` | 납기일 | 납기 캘린더 기준 |
| `note` | 비고 | 기타, 방폭 여부 등 |
| `source_sheet` | — | 읽어 온 시트 이름 (예: 2026(NTI)) |

### SalesOrder — 수주서 (PDF 1장 = 1건)

| 필드 | PDF 필드 | 설명 |
|---|---|---|
| `sales_no` (unique, 확인 필요) | 판매번호 | 예: NTK-SO-260000 |
| `order_no` | 수주번호 | 빈칸 가능 |
| `order_doc_no` | 수주서류 | 번호만 저장 (예: `#26024 파일이름.p…` → 26024) |
| `order_date` | 수주일 | 샘플에서 확인 (2026-10-18 추가) |
| `business_type_raw` | 사업구분 | 원문 (예: 상하수도(지자체)) |
| `industry` | — | 7개 분야 중 하나로 변환한 값 |
| `customer` | 판매처 | |
| `final_orderer` | 최종발주처/EPC | |
| `project_name` | 사업명 | |
| `delivery_date` | 납품일/출장일 | |
| `due_date` | 납기일 | |
| `note` | 제작관련 공통사양/비고 | |

### SalesOrderItem — 수주서 제품정보 (수주서 1건에 여러 개)

| 필드 | PDF 필드 |
|---|---|
| `order` (FK → SalesOrder) | |
| `product_name` | 품명 (예: 제수 150A: NTI-03) |
| `quantity` | 수량 |
| `power` | 전원 |
| `flange` | Flange |
| `rpm_ot` | RPM/OT |
| `stem_bush` | 스템/부시가공 |

- 제조내역과 수주서를 잇는 기준 번호는 **확인 필요**이므로, 처음에는 두 테이블을 FK로 묶지 않고 조회 시 번호로 찾아 보완한다.

### 산업 분야 대응표

- 7개 분야: 상하수도, 발전소, 가스, 오일, 석유, 민간 플랜트, 기타
- 사업구분 원문 → 분야 대응은 설정 파일 또는 작은 테이블로 관리한다. 대응 기준은 확인 필요.

## 4. 서비스팀

### TripReport — 출장보고서 (1건 = 출장 1회)

| 필드 | 보고서 필드 |
|---|---|
| `start_date`, `end_date` | 출장 시작일·종료일 (월 집계는 start_date 기준) |
| `extra_trip` | 추가 출장 |
| `paid_type` | 비고 > 비용청구 유무 (유상/무상) |
| `requester_type` | 요청처 구분 |
| `requester` | 요청처 |
| `region` | 시·도 (대응표 또는 확인 화면에서 지정) |
| `district` | 시·군 (도 지역만. 특별·광역시·세종시는 빈 값) |
| `work_type` | 작업 구분 (예: 수리) |
| `spec` | 사양 |
| `serial_no_raw` | 일련번호 원문 (예: A80018377702) |
| `fault_description` | 고장 내용 (자유 서술) |
| `work_description` | 작업 내용 |
| `work_result` | 작업 결과 |
| `author` | 작성자 |
| `input_method` | 입력 방식: `pdf`(PDF 업로드) / `manual`(직접 입력). 기존 보고서는 `pdf` |

### TripReportCompanion — 동행자 (여러 명)

- `report` (FK), `name`
- 담당자 순위는 작성자와 동행자를 합친 뒤 **보고서 1건당 1인 1회**로 센다.

### TripReportProduct — 제품 목록 (여러 개)

- `report` (FK), `model_name` (예: AVA03), `quantity`

### TripReportPart — 부품 사용 내역 (여러 개)

- `report` (FK), `part_name`, `quantity`(있을 경우)

### PartPrice — 부품 단가 (출처 확인 전, 웹 직접 입력)

- `part_name`, `unit_price`(원 단위 정수), `effective_date`(적용 시작일)
- 같은 부품·같은 적용 시작일은 한 줄만(unique). 단가가 바뀌면 새 적용 시작일로 한 줄을 더한다 → 기간별 변동
- `part_name`은 TripReportPart.part_name과 같은 이름이어야 사용 내역과 연결된다(FK 없음)
- `source`(출처: `manual` 직접 입력 / `quote` 견적서), `quote_no`(견적 번호), `quote_item`(견적서 품명 원문) — 견적서 업로드 중복 기준 = 견적 번호 + 견적서 품명
- `quote_company`(업체명 = 방문한 회사), `quote_project`(사업명), `quote_note`(비고) — 견적 단가가 달라진 이유를 참고하는 정보

- `catalog_item`(FK → PartCatalogItem, 2026-11-02) — 단가표 파트넘버와 연결. 같은 부품·같은 업체(`quote_company`)·같은 적용 시작일은 한 줄만(단가표에 연결된 줄 기준). 업체가 다르면 같은 날짜도 따로 저장 → 출장지별 비교

### PartCatalogItem — 부품 단가표 (2026-11-02, 실제 값은 로컬 DB에만)

- `part_no`(파트넘버, 검색 기준), `category`(분류), `name`(품명), `applies_to`(적용 모델 원문), `list_price`(단가표 기준단가, 없으면 비움), `list_price_date`(단가표 기준일)
- `discount_rate`(%)·`extra_price`(원) — 부품마다 따로 정할 때만 채움. 비어 있으면 PriceStandard 기본값
- `sort_order`(단가표 순서). (`part_no`, `name`) unique — 원본에 같은 파트넘버가 두 품목에 쓰인 경우가 있어 품명까지 묶음(확인 필요)

### PriceStandard — 뉴토크 기준값 전체 기본값 (한 줄)

- `default_discount_rate`(%), `default_extra_price`(원), `low_alert_rate`(크게 낮음 표시 기준 %, 임시 10 — 2026-11-02)

### PartListPrice — 단가표 개정 이력 (2026-11-02)

- `item`(FK PartCatalogItem), `list_price`(없으면 비움), `effective_date`(단가표 기준일). (`item`, `effective_date`) unique
- 단가표를 새 기준일로 넣으면 한 줄 더함(예전 값은 지우지 않음). PartCatalogItem의 `list_price`·`list_price_date`는 가장 최근 기준일 값
- 업체 단가는 **견적 적용 시작일 당시 단가표**의 기준값과 비교(단가표보다 이른 견적은 가장 오래된 단가표). 할인율·추가단가는 이력 없이 지금 설정

### QuotePartAlias — 견적서 품명 → 단가표 부품 대응표

- `quote_item` (unique), `part_name`, `catalog_item`(FK, 2026-11-02)
- 견적서 업로드 확인 화면에서 고른 파트넘버를 기억해 다음 견적서부터 자동으로 채운다

### RequesterRegion — 요청처 → 시·도·시·군 대응표

- `requester` (unique), `region`, `district`

## 4-1. 제품 가격 (pricing 앱, 2026-11-02 — 실제 값은 로컬 DB에만)

### ProductPriceSetting — 가격 계산 기준값 (적용일별 한 줄, 가장 최근 적용일 사용)

- `effective_date`(unique), `exchange_rate`, `customs_factor`, `sga_rate`(%), `margin`(나누는 값), `special_discount_rate`(%), `price_round_unit`(올림 단위, 1000), `commission_rate`(%), `commission_unit`(버림 단위, 10000), `margin_choices`(시뮬레이션 선택 목록)
- `note`(변경 사유), `created_by`(공통 칸, 화면에서 바꾼 사람 — 계산표 파일로 넣은 줄은 비움) — 2026-11-02. 화면에서 바꾸면 새 적용일로 한 줄 더해 변경 기록이 남음

### PricingAccessLog — 제품 단가·원가 열람 기록 (2026-11-02)

- `user`(FK), `viewed_at`. 같은 사람은 10분에 한 번만 남김(시뮬레이션마다 API를 부르므로)

### ProductModel — 모델별 원재료 가격

- `model_name`(unique), `series`, `assembly_usd`, `complete_usd`, `sale_price`(커미션 계산용 판매금액, 없으면 비움), `sort_order`
- 단계별 금액(원화~특별할인가)은 저장하지 않고 기준값으로 계산한다 → 환율 등을 바꾸면 모두 다시 계산

### ProductOption — 옵션 가격

- `name`(unique), `price_usd` (단위·더하는 단계 확인 필요)

## 5. 업로드 공통

### UploadBatch — 업로드 기록

| 필드 | 설명 |
|---|---|
| `kind` | `manufacturing_excel` / `sales_order_pdf` / `trip_report_pdf` / `quote_pdf` / `trip_report_excel` / `history_excel` |
| `file_name` | 원본 파일 이름 |
| `status` | `extracted`(확인 대기) / `saved`(저장 완료) / `cancelled` |
| `extracted_data` | 추출 결과 (JSON, 확인·수정 단계에서 사용). `columns`, `rows`(행마다 values·errors·duplicate·excluded), `skipped_count` |
| `saved_count` | 저장한 행 수 |
| `uploaded_by`, `uploaded_at` | |

- 실제 기업 원본 파일을 서버에 보관할지, 추출 후 버릴지는 팀이 정한다. 원본 파일은 Git에 올리지 않는다.

## 변경 기록

- 2026-10-18: 지침(2026-10-17) 기준으로 최초 작성
- 2026-10-18: Phase 3 구현. `model_code`(뒤 2자리) → `model_name`(전체 모델명)으로 변경 — 화면 표시와 수주서 품명(예: NTI-03) 대조에 전체 이름이 필요해서. 샘플 엑셀에서 확인한 `customer_order_no` 추가. 공통 필드는 `common/models.py`의 TimeStampedModel로 구현
- 2026-10-18: UploadBatch 구현. `uploaded_by`·`uploaded_at`은 공통 필드 `created_by`·`created_at`으로 대신함. 원본 파일은 보관하지 않기로 결정
- 2026-10-18: SalesOrder·SalesOrderItem 구현. `order_date`(수주일) 추가. 제조내역과는 FK 없이 "수주서류 번호 = PO번호"로 조회 시 찾아 플랜지를 보완(임시)
- 2026-10-18: 서비스팀 테이블 구현. `spec`·`serial_no_raw`는 보고서가 아니라 **제품(TripReportProduct)**에 둠 — 보고서 1건에 제품이 여러 개일 수 있고 제품마다 사양·일련번호가 다르기 때문. `purpose`(출장 목적) 추가. PartPrice는 단가 출처 확인 전이라 만들지 않음
- 2026-10-19: TripReport·RequesterRegion에 `district`(시·군) 추가
- 2026-10-21: PartPrice 구현 — 단가 출처 확인 전이지만 웹 직접 입력으로 먼저 만듦(사용자 요청). 적용 시작일 이력 방식
- 2026-10-21: TripReport에 `input_method`(입력 방식) 추가 — 직접 입력과 PDF 업로드를 구분
- 2026-10-26: PartPrice에 `source`·`quote_no`·`quote_item`·`quote_company`·`quote_project`·`quote_note` 추가, QuotePartAlias 추가, UploadBatch.kind에 `quote_pdf` 추가
- 2026-11-02: PartCatalogItem·PriceStandard 추가, PartPrice·QuotePartAlias에 `catalog_item` 추가. PartPrice 중복 기준을 "부품 + 업체 + 날짜"로 변경
- 2026-11-02: pricing 앱(ProductPriceSetting·ProductModel·ProductOption) 추가
- 2026-11-02: PartListPrice(단가표 개정 이력, 기존 값은 첫 이력으로 옮김), PriceStandard.`low_alert_rate`, ProductPriceSetting.`note`, PricingAccessLog 추가(사용자 요청, 2순위 개선)
- 2026-11-04: 경영지원팀 MonthlyFinance 구현 — 조원 저장소 설계를 따라 `status`(임시저장·확정)·`cash_balance` 추가, 그 외 지출을 ExpenseCategory·OtherExpense로 나눔, `receivables`는 미수금 단계로 미룸 (사용자 결정: 조원 경영지원팀 기능 옮기기)
- 2026-11-04: LedgerEntry(경영지원 관리 장부)·AuditLog(변경 기록) 추가 — 조원 저장소 설계를 따름 (사용자 요청)
- 2026-11-04: AnnualSalesTarget에 분기 목표(`q1_target`~`q4_target`, 선택)·`headcount`(선택) 추가, ExpenseCategory에 `updated_at` 추가 — 조원 저장소 설계를 따름(목표·항목 설정 3단계)
- 2026-11-04: Receivable(미수금 건별 기록) 추가 — 조원 저장소 설계를 따름 (5단계)
- 2026-11-04: LedgerEntry에 `deleted_by`·`updated_by` 추가 (장부 화면, 6-1단계)
- 2026-11-04: AiComment(AI 분석 코멘트) 추가 — 조원 저장소 설계를 따름 (8단계)
