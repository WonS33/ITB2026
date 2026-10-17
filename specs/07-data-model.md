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
| `role` | `ceo` / `management` / `admin` / `leader` / `member` |
| `view_teams` | 열람 가능한 팀 목록 (`production`, `service`) |
| `edit_teams` | 수정 가능한 팀 목록 (`production`, `service`) |
| `must_change_password` | 첫 로그인 비밀번호 변경 안내 여부 |

자세한 규칙은 [02-users-permissions.md](02-users-permissions.md).

## 2. 경영지원팀

### AnnualSalesTarget — 연간 목표매출

| 필드 | 설명 |
|---|---|
| `year` (unique) | 연도 |
| `target_amount` | 연간 목표매출액(원) |

### MonthlyFinance — 월별 실적

| 필드 | 설명 |
|---|---|
| `year`, `month` (함께 unique) | 연월 |
| `product_sales` | 제품 매출액 |
| `merchandise_sales` | 상품 매출액 |
| `service_sales` | 용역 매출액 |
| `merchandise_purchase` | 상품 매입액 |
| `material_purchase` | 원재료 매입액 |
| `expense` | 경비 지출액 |
| `other_expense` | 그 외 지출액(광고선전비, 접대비 등) |
| `receivables` | 미수금 통계 (형식 확인 필요 → 우선 월 합계 금액) |

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
| `work_type` | 작업 구분 (예: 수리) |
| `spec` | 사양 |
| `serial_no_raw` | 일련번호 원문 (예: A80018377702) |
| `fault_description` | 고장 내용 (자유 서술) |
| `work_description` | 작업 내용 |
| `work_result` | 작업 결과 |
| `author` | 작성자 |

### TripReportCompanion — 동행자 (여러 명)

- `report` (FK), `name`
- 담당자 순위는 작성자와 동행자를 합친 뒤 **보고서 1건당 1인 1회**로 센다.

### TripReportProduct — 제품 목록 (여러 개)

- `report` (FK), `model_name` (예: AVA03), `quantity`

### TripReportPart — 부품 사용 내역 (여러 개)

- `report` (FK), `part_name`, `quantity`(있을 경우)

### PartPrice — 부품 단가 (출처 확인 필요)

- `part_name`, `unit_price`, `effective_date`
- 단가 출처(견적서, 부품 단가표)가 확인된 뒤 만든다.

### RequesterRegion — 요청처 → 시·도 대응표

- `requester` (unique), `region`

## 5. 업로드 공통

### UploadBatch — 업로드 기록

| 필드 | 설명 |
|---|---|
| `kind` | `manufacturing_excel` / `sales_order_pdf` / `trip_report_pdf` / `trip_report_excel` / `history_excel` |
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
