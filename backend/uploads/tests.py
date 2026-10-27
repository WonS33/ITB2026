from datetime import date
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from accounts.models import User
from production.models import ManufacturingRecord

from .handlers import HANDLERS
from .models import UploadBatch
from .sample_files import build_manufacturing_workbook

P = User.Team.PRODUCTION
S = User.Team.SERVICE

ROWS = [
    {"no": 1, "model": "04", "bush": 301008, "made": date(2026, 1, 9), "due": date(2026, 1, 15), "po": "26006"},
    {"no": 2, "model": "02", "made": date(2026, 1, 9), "note": "가상 비고"},
]


def excel_file(rows=ROWS, **kwargs):
    return SimpleUploadedFile("제조내역.xlsx", build_manufacturing_workbook(rows, **kwargs))


class ManufacturingParseTests(APITestCase):
    handler = HANDLERS["manufacturing_excel"]

    def test_values_use_cell_format_prefix(self):
        rows, skipped = self.handler.parse(BytesIO(build_manufacturing_workbook(ROWS)))
        v = rows[0]["values"]
        self.assertEqual(v["serial_full"], "N82260001")  # '0001' + "N8226"
        self.assertEqual(v["model_name"], "NTI-04")
        self.assertEqual(v["inspection_no"], "NTK26001")
        self.assertEqual(v["po_no"], "26006")  # '#' 제거
        self.assertEqual(v["bush_machining"], "301008")
        self.assertEqual(v["manufactured_date"], "2026-01-09")
        self.assertEqual(rows[0]["row_no"], 10)  # 안내·두 줄 제목 다음 줄부터
        self.assertEqual(skipped, 3)  # 일련번호 없는 행 제외

    def test_date_stored_as_number(self):
        rows, _ = self.handler.parse(BytesIO(build_manufacturing_workbook(ROWS, date_as_number=True)))
        self.assertEqual(rows[0]["values"]["manufactured_date"], "2026-01-09")  # 46031 → 날짜

    def test_not_a_manufacturing_excel(self):
        from openpyxl import Workbook
        buffer = BytesIO()
        Workbook().save(buffer)
        buffer.seek(0)
        with self.assertRaises(ValueError):
            self.handler.parse(buffer)

    def test_validate(self):
        errors = self.handler.validate({"serial_full": "X1", "manufactured_date": "", "due_date": "2026/01/01",
                                        "bush_machining": "12"})
        self.assertEqual(set(errors), {"serial_full", "manufactured_date", "due_date", "bush_machining"})


class UploadFlowTests(APITestCase):
    def login(self, role=User.Role.LEADER, view=(P,), edit=(P,)):
        user = User.objects.create_user(f"u{User.objects.count()}", password="x", role=role,
                                        view_teams=list(view), edit_teams=list(edit))
        self.client.force_authenticate(user)
        return user

    def upload(self, file=None, kind="manufacturing_excel"):
        return self.client.post("/api/uploads/", {"kind": kind, "file": file or excel_file()}, format="multipart")

    def test_upload_extract_confirm(self):
        self.login()
        res = self.upload()
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["summary"]["to_save"], 2)
        self.assertEqual(ManufacturingRecord.objects.count(), 0)  # 추출 단계에서는 저장 안 함

        res = self.client.post(f"/api/uploads/{res.data['id']}/confirm/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["saved_count"], 2)
        record = ManufacturingRecord.objects.get(serial_full="N82260001")
        self.assertEqual((record.serial_short, record.model_name, record.source_sheet), ("0001", "NTI-04", "2026(NTI)"))
        self.assertEqual(record.manufactured_date, date(2026, 1, 9))

    def test_same_file_twice_is_not_duplicated(self):
        self.login()
        first = self.upload()
        self.client.post(f"/api/uploads/{first.data['id']}/confirm/")
        second = self.upload()
        self.assertEqual(second.data["summary"]["duplicate_rows"], 2)
        self.assertEqual(second.data["summary"]["to_save"], 0)
        self.client.post(f"/api/uploads/{second.data['id']}/confirm/")
        self.assertEqual(ManufacturingRecord.objects.count(), 2)

    def test_fix_error_then_save(self):
        self.login()
        rows = ROWS + [{"no": 3, "made": None}]  # 제조년월 누락
        res = self.upload(excel_file(rows))
        self.assertEqual(res.data["summary"]["error_rows"], 1)
        batch_id = res.data["id"]
        bad = next(r for r in res.data["rows"] if r["errors"])
        self.assertIn("manufactured_date", bad["errors"])

        self.assertEqual(self.client.post(f"/api/uploads/{batch_id}/confirm/").status_code, 400)

        res = self.client.patch(f"/api/uploads/{batch_id}/",
                                {"rows": [{"id": bad["id"], "values": {"manufactured_date": "2026-02-01"}}]},
                                format="json")
        self.assertEqual(res.data["summary"]["error_rows"], 0)
        self.client.post(f"/api/uploads/{batch_id}/confirm/")
        self.assertEqual(ManufacturingRecord.objects.count(), 3)

    def test_exclude_row(self):
        self.login()
        res = self.upload(excel_file(ROWS + [{"no": 3, "made": None}]))
        bad = next(r for r in res.data["rows"] if r["errors"])
        res = self.client.patch(f"/api/uploads/{res.data['id']}/", {"rows": [{"id": bad["id"], "excluded": True}]},
                                format="json")
        self.assertEqual(res.data["summary"]["excluded_rows"], 1)
        self.assertEqual(self.client.post(f"/api/uploads/{res.data['id']}/confirm/").data["saved_count"], 2)

    def test_duplicate_inside_file(self):
        self.login()
        res = self.upload(excel_file([ROWS[0], ROWS[0]]))
        self.assertEqual(res.data["summary"]["error_rows"], 1)

    def test_cancel_and_processed_batch(self):
        self.login()
        batch_id = self.upload().data["id"]
        self.assertEqual(self.client.post(f"/api/uploads/{batch_id}/cancel/").status_code, 200)
        self.assertEqual(UploadBatch.objects.get(pk=batch_id).status, "cancelled")
        self.assertEqual(self.client.post(f"/api/uploads/{batch_id}/confirm/").status_code, 400)

    def test_permissions(self):
        self.assertEqual(self.upload().status_code, 401)
        self.login(User.Role.MEMBER, view=(P,), edit=())  # 생산팀원: 열람만
        self.assertEqual(self.upload().status_code, 403)
        self.login(User.Role.LEADER, view=(S,), edit=(S,))  # 서비스팀장
        self.assertEqual(self.upload().status_code, 403)
        self.login(User.Role.MEMBER, view=(User.Team.MANAGEMENT,), edit=())  # 경영지원팀원: 전체 수정
        self.assertEqual(self.upload().status_code, 201)

    def test_other_users_batch_needs_permission(self):
        self.login()
        batch_id = self.upload().data["id"]
        self.login(User.Role.MEMBER, view=(P,), edit=())
        self.assertEqual(self.client.post(f"/api/uploads/{batch_id}/confirm/").status_code, 403)

    def test_bad_inputs(self):
        self.login()
        self.assertEqual(self.upload(kind="unknown").status_code, 400)
        self.assertEqual(self.upload(SimpleUploadedFile("a.csv", b"1,2")).status_code, 400)
        self.assertEqual(self.upload(SimpleUploadedFile("a.xlsx", b"not excel")).status_code, 400)


# ---------------------------------------------------------------- 수주서 PDF (Phase 7)
import os
import unittest
from unittest import mock

from django.conf import settings

from production.industry_map import to_industry
from production.models import SalesOrder

from .handlers.pdf_form import CHAR_MAP, FormPage, Word

SAMPLE_PDF = os.path.join(settings.BASE_DIR.parent, "samples", "생산팀 제조내역 샘플_2.pdf")


class PdfFormTests(APITestCase):
    def test_char_map_restores_digits_and_symbols(self):
        self.assertEqual("NTK-SO-".translate(CHAR_MAP), "NTK-SO-260000")
        self.assertEqual("150A 3 4".translate(CHAR_MAP), "150A: 3, 4.")

    def test_value_below_label_until_next_label(self):
        page = FormPage([
            Word("판매번호", 28, 60, 100, 108), Word("판매처", 400, 420, 100, 108),
            Word("NTK-SO-1", 28, 90, 116, 124), Word("가람", 400, 420, 116, 124),
            Word("사업명", 28, 60, 140, 148), Word("가상 사업", 28, 80, 156, 164),
            Word("둘째 줄", 28, 60, 166, 174), Word("제품정보", 28, 60, 200, 208),
            Word("다른 구역", 28, 60, 216, 224),
        ], 595, 842)
        labels, headings = ["판매번호", "판매처", "사업명"], ["제품정보"]
        self.assertEqual(page.value("판매번호", labels, headings), "NTK-SO-1")  # 같은 줄 오른쪽 칸은 안 섞임
        self.assertEqual(page.value("판매처", labels, headings), "가람")
        self.assertEqual(page.value("사업명", labels, headings), "가상 사업\n둘째 줄")  # 구역 제목 전까지
        self.assertIsNone(page.value("없는 항목", labels, headings))

    def test_table(self):
        page = FormPage([
            Word("품명", 34, 48, 400, 408), Word("수량", 375, 390, 400, 408),
            Word("제수 150A: NTI-03", 34, 98, 420, 428), Word("3", 375, 380, 420, 428),
            Word("합계 : 3", 375, 400, 460, 468),
        ], 595, 842)
        self.assertEqual(page.table(["품명", "수량"], ["합계"]), [{"품명": "제수 150A: NTI-03", "수량": "3"}])

    def test_industry_map(self):
        self.assertEqual(to_industry("상하수도(지자체)"), "상하수도")
        self.assertEqual(to_industry("석유화학"), "석유")
        self.assertEqual(to_industry("알 수 없는 값"), "기타")


def order_rows(sales_no="NTK-SO-260000", customer="가람상수도사업소", items=(("제수 150A: NTI-03", "3"),)):
    base = {"sales_no": sales_no, "order_date": "2026-01-27", "business_type_raw": "상하수도(지자체)",
            "industry": "상하수도", "customer": customer, "final_orderer": "가람", "project_name": "가상 사업",
            "order_no": "", "due_date": "2026-03-13", "delivery_date": "", "order_doc_no": "26024", "note": ""}
    return [{"row_no": 1, "sheet": "1쪽", "values": {**base, "item_no": str(i), "product_name": name, "quantity": qty,
             "power": "380/3/60", "flange": "F10A", "rpm_ot": "29", "stem_bush": ""}}
            for i, (name, qty) in enumerate(items, start=1)]


class SalesOrderUploadTests(APITestCase):
    def setUp(self):
        self.client.force_authenticate(User.objects.create_user(
            "leader", password="x", role=User.Role.LEADER, view_teams=[P], edit_teams=[P]))

    def upload(self, rows):
        with mock.patch("uploads.handlers.sales_order_pdf.SalesOrderPdfHandler.parse", return_value=(rows, 0)):
            return self.client.post("/api/uploads/", {"kind": "sales_order_pdf",
                                                      "file": SimpleUploadedFile("수주서.pdf", b"%PDF")},
                                    format="multipart")

    def test_save_order_with_items_and_skip_duplicate(self):
        res = self.upload(order_rows(items=(("제수 150A: NTI-03", "3"), ("제수 200A: NTI-04", "1"))))
        self.assertEqual(res.data["summary"]["to_save"], 2)
        self.client.post(f"/api/uploads/{res.data['id']}/confirm/")
        order = SalesOrder.objects.get(sales_no="NTK-SO-260000")
        self.assertEqual(sorted((i.product_name, i.quantity) for i in order.items.all()),
                         [("제수 150A: NTI-03", 3), ("제수 200A: NTI-04", 1)])

        again = self.upload(order_rows())
        self.assertEqual(again.data["summary"]["duplicate_rows"], 1)  # 같은 판매번호 → 건너뜀

    def test_truncated_value_must_be_fixed(self):
        res = self.upload(order_rows(customer="가람상수도사업소 …"))
        row = res.data["rows"][0]
        self.assertIn("customer", row["errors"])
        res = self.client.patch(f"/api/uploads/{res.data['id']}/",
                                {"rows": [{"id": row["id"], "values": {"customer": "가람상수도사업소"}}]},
                                format="json")
        self.assertEqual(res.data["summary"]["error_rows"], 0)

    def test_rows_of_same_order_must_match(self):
        rows = order_rows(items=(("제수 150A", "3"), ("제수 200A", "1")))
        rows[1]["values"]["customer"] = "다른 판매처"
        res = self.upload(rows)
        self.assertIn("customer", res.data["rows"][1]["errors"])

    def test_quantity_and_industry_validation(self):
        rows = order_rows(items=(("제수 150A", "0"),))
        rows[0]["values"]["industry"] = "우주"
        errors = self.upload(rows).data["rows"][0]["errors"]
        self.assertIn("quantity", errors)
        self.assertIn("industry", errors)

    def test_service_leader_cannot_upload_sales_order(self):
        self.client.force_authenticate(User.objects.create_user(
            "svc", password="x", role=User.Role.LEADER, view_teams=[S], edit_teams=[S]))
        self.assertEqual(self.upload(order_rows()).status_code, 403)


@unittest.skipUnless(os.path.exists(SAMPLE_PDF), "실제 샘플 PDF가 없는 PC에서는 건너뜀 (samples/는 Git 제외)")
class RealSampleSalesOrderTests(APITestCase):
    """실제 샘플 PDF 읽기 확인. 실제 기업 값은 코드에 적지 않고 형식만 확인한다 (CLAUDE.md 7절)."""

    def test_parse_real_sample(self):
        import re

        from production.industry_map import INDUSTRIES

        from .handlers import HANDLERS

        with open(SAMPLE_PDF, "rb") as f:
            rows, _ = HANDLERS["sales_order_pdf"].parse(f)
        v = rows[0]["values"]
        self.assertRegex(v["sales_no"], r"^NTK-SO-\d+$")  # 숫자 특수 코드가 복원됨
        self.assertRegex(v["due_date"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertRegex(v["order_doc_no"], r"^\d+$")  # "#번호 파일이름…" → 번호만
        self.assertRegex(v["quantity"], r"^[1-9]\d*$")
        self.assertIn(":", v["product_name"])  # ":" 특수 코드가 복원됨 (예: 제수 150A: NTI-03)
        self.assertIn(v["industry"], INDUSTRIES)
        self.assertTrue(v["customer"].endswith("…"))  # 잘린 값이 그대로 잡혀 확인 화면에서 오류로 표시됨
        self.assertTrue(re.match(r"^F\d+", v["flange"]))

class DuplicateRowsSkipValidationTests(APITestCase):
    """이미 저장된 판매번호의 행은 오류(잘린 값 등)를 표시하지 않고 '중복(건너뜀)'으로만 본다"""

    setUp = SalesOrderUploadTests.setUp
    upload = SalesOrderUploadTests.upload

    def test_saved_order_with_truncated_value_is_just_duplicate(self):
        res = self.upload(order_rows())
        self.client.post(f"/api/uploads/{res.data['id']}/confirm/")
        again = self.upload(order_rows(customer="가람상수도사업소 …"))
        self.assertEqual(again.data["summary"]["error_rows"], 0)
        self.assertEqual(again.data["summary"]["duplicate_rows"], 1)
        self.assertEqual(self.client.post(f"/api/uploads/{again.data['id']}/confirm/").data["saved_count"], 0)


# ---------------------------------------------------------------- 출장보고서 PDF (Phase 8)
from service.models import RequesterRegion, TripReport

TRIP_SAMPLE_PDF = os.path.join(settings.BASE_DIR.parent, "samples", "서비스팀 출장보고서 샘플.pdf")


def trip_rows(**overrides):
    values = {"start_date": "2026-09-29", "end_date": "2026-09-30", "requester": "가람산업단지", "region": "충청북도",
              "district": "청주시", "paid_type": "유상", "author": "김가상 대리", "companions": "김가상 대리\n이가상 사원",
              "products": "AVA03 | 380V/3Ph/60Hz, 29rpm | A80018377702 | 1", "parts": "Main Board\nPower Board",
              "work_type": "수리", "requester_type": "검색 불가", "extra_trip": "없음", "purpose": "가상 A/S",
              "fault_description": "1. 메인보드 고장", "work_description": "1. 메인보드 교체", "work_result": "정상작동"}
    values.update(overrides)
    return [{"row_no": 1, "sheet": "1쪽", "values": values}]


class TripReportUploadTests(APITestCase):
    def setUp(self):
        self.client.force_authenticate(User.objects.create_user(
            "svc_leader", password="x", role=User.Role.LEADER, view_teams=[S], edit_teams=[S]))

    def upload(self, rows):
        with mock.patch("uploads.handlers.trip_report_pdf.TripReportPdfHandler.parse", return_value=(rows, 0)):
            return self.client.post("/api/uploads/", {"kind": "trip_report_pdf",
                                                      "file": SimpleUploadedFile("출장보고서.pdf", b"%PDF")},
                                    format="multipart")

    def test_save_report_with_children_and_remember_region(self):
        res = self.upload(trip_rows())
        self.assertEqual(res.data["summary"]["to_save"], 1)
        region_col = next(c for c in res.data["columns"] if c["key"] == "region")
        self.assertIn("제주특별자치도", region_col["choices"])  # 선택 목록으로 보여줌
        district_col = next(c for c in res.data["columns"] if c["key"] == "district")
        self.assertEqual(district_col["choices_by"], "region")  # 시·도에 따라 시·군 목록이 바뀜
        self.assertIn("강릉시", district_col["choices_map"]["강원특별자치도"])
        self.client.post(f"/api/uploads/{res.data['id']}/confirm/")

        report = TripReport.objects.get()
        self.assertEqual((report.region, report.district, report.paid_type, report.author),
                         ("충청북도", "청주시", "유상", "김가상 대리"))
        self.assertEqual(sorted(c.name for c in report.companions.all()), ["김가상 대리", "이가상 사원"])
        product = report.products.get()
        self.assertEqual((product.model_name, product.spec, product.serial_no_raw, product.quantity),
                         ("AVA03", "380V/3Ph/60Hz, 29rpm", "A80018377702", 1))
        self.assertEqual(sorted(p.part_name for p in report.parts.all()), ["Main Board", "Power Board"])
        remembered = RequesterRegion.objects.get(requester="가람산업단지")
        self.assertEqual((remembered.region, remembered.district), ("충청북도", "청주시"))

    def test_duplicate_by_start_date_and_requester(self):
        """기준: 출장 시작일 + 요청처 — 작성자·동행자가 달라도 같은 출장으로 본다"""
        res = self.upload(trip_rows())
        self.client.post(f"/api/uploads/{res.data['id']}/confirm/")
        changed = self.upload(trip_rows(author="박다른 과장", companions="최다른 사원"))
        self.assertEqual(changed.data["summary"]["duplicate_rows"], 1)
        self.assertTrue(changed.data["allow_duplicate_override"])
        other_day = self.upload(trip_rows(start_date="2026-10-01", end_date="2026-10-02"))
        self.assertEqual(other_day.data["summary"]["to_save"], 1)

    def test_confirm_not_duplicate_saves_second_trip(self):
        """같은 날 같은 곳에 실제로 두 번 간 경우: '중복 아님'을 체크하면 저장"""
        res = self.upload(trip_rows())
        self.client.post(f"/api/uploads/{res.data['id']}/confirm/")
        again = self.upload(trip_rows(author="박다른 과장"))
        row = again.data["rows"][0]
        self.assertTrue(row["matches_existing"])
        res = self.client.patch(f"/api/uploads/{again.data['id']}/",
                                {"rows": [{"id": row["id"], "allow_duplicate": True}]}, format="json")
        self.assertEqual(res.data["summary"]["to_save"], 1)
        self.assertEqual(self.client.post(f"/api/uploads/{again.data['id']}/confirm/").data["saved_count"], 1)
        self.assertEqual(TripReport.objects.count(), 2)

    def test_two_pages_same_trip_in_one_file(self):
        rows = trip_rows() + [{**trip_rows()[0], "row_no": 2}]
        res = self.upload(rows)
        second = res.data["rows"][1]
        self.assertIn("start_date", second["errors"])  # 파일 안 중복
        res = self.client.patch(f"/api/uploads/{res.data['id']}/",
                                {"rows": [{"id": second["id"], "allow_duplicate": True}]}, format="json")
        self.assertEqual(res.data["summary"]["to_save"], 2)

    def test_validation(self):
        errors = self.upload(trip_rows(region="", paid_type="반반", end_date="2026-09-01",
                                       parts="Magnetic Contactor (TR Cont…", products="AVA03 | | | 0"))
        errors = errors.data["rows"][0]["errors"]
        self.assertEqual(set(errors), {"region", "paid_type", "end_date", "parts", "products"})

    def test_district_must_match_region(self):
        errors = lambda **kw: self.upload(trip_rows(**kw)).data["rows"][0]["errors"]
        self.assertEqual(errors(district="")["district"], "시·군을 골라 주세요.")  # 도는 시·군 필수
        self.assertIn("district", errors(district="강릉시"))  # 충청북도에 없는 시·군
        self.assertEqual(errors(region="서울특별시", district=""), {})  # 특별·광역시는 시·군 없음
        self.assertIn("district", errors(region="서울특별시", district="청주시"))

    def test_production_leader_cannot_upload_trip_report(self):
        self.client.force_authenticate(User.objects.create_user(
            "prod", password="x", role=User.Role.LEADER, view_teams=[P], edit_teams=[P]))
        self.assertEqual(self.upload(trip_rows()).status_code, 403)


@unittest.skipUnless(os.path.exists(TRIP_SAMPLE_PDF), "실제 샘플 PDF가 없는 PC에서는 건너뜀 (samples/는 Git 제외)")
class RealSampleTripReportTests(APITestCase):
    """실제 샘플 PDF 읽기 확인. 실제 기업 값은 코드에 적지 않고 형식만 확인한다 (CLAUDE.md 7절)."""

    def test_parse_real_sample(self):
        from .handlers import HANDLERS
        from .handlers.trip_report_pdf import PAID_TYPES

        handler = HANDLERS["trip_report_pdf"]
        with open(TRIP_SAMPLE_PDF, "rb") as f:
            v = handler.parse(f)[0][0]["values"]
        self.assertRegex(v["start_date"], r"^\d{4}-\d{2}-\d{2}$")  # 숫자 특수 코드가 복원됨
        self.assertGreaterEqual(v["end_date"], v["start_date"])
        self.assertIn(v["paid_type"], PAID_TYPES)
        self.assertTrue(v["requester"] and v["author"])
        self.assertEqual(v["region"], "")  # 대응표에 없으면 비어 있음 → 확인 화면에서 고름
        self.assertRegex(v["products"], r"^\w+ \| .+, .+ \| \w+ \| \d+$")  # "," 특수 코드 복원, 표 4칸
        self.assertTrue(any(line.endswith("…") for line in v["parts"].split("\n")))  # 잘린 부품명이 잡힘
        self.assertGreater(v["fault_description"].count("\n"), 1)  # 여러 줄 값

        # 대응표에 요청처가 있으면 시·도·시·군을 자동으로 채운다
        RequesterRegion.objects.create(requester=v["requester"], region="충청북도", district="청주시")
        with open(TRIP_SAMPLE_PDF, "rb") as f:
            filled = handler.parse(f)[0][0]["values"]
        self.assertEqual((filled["region"], filled["district"]), ("충청북도", "청주시"))

class OverrideNotAllowedForUniqueNumbersTests(APITestCase):
    """일련번호처럼 고유 번호가 기준인 종류는 '중복 아님'을 보내도 무시하고 건너뛴다"""

    def test_manufacturing_ignores_allow_duplicate(self):
        self.client.force_authenticate(User.objects.create_user(
            "p", password="x", role=User.Role.LEADER, view_teams=[P], edit_teams=[P]))
        first = self.client.post("/api/uploads/", {"kind": "manufacturing_excel", "file": excel_file()}, format="multipart")
        self.client.post(f"/api/uploads/{first.data['id']}/confirm/")
        again = self.client.post("/api/uploads/", {"kind": "manufacturing_excel", "file": excel_file()}, format="multipart")
        self.assertFalse(again.data["allow_duplicate_override"])
        changes = [{"id": r["id"], "allow_duplicate": True} for r in again.data["rows"]]
        res = self.client.patch(f"/api/uploads/{again.data['id']}/", {"rows": changes}, format="json")
        self.assertEqual(res.data["summary"]["duplicate_rows"], 2)
        self.assertEqual(self.client.post(f"/api/uploads/{again.data['id']}/confirm/").data["saved_count"], 0)


# ---------------------------------------------------------------- 유상 A/S 견적서 PDF → 부품 단가
from service.models import PartPrice, QuotePartAlias

from .handlers.quote_pdf import bottom_note, read_items, value_right_of

QUOTE_SAMPLE_PDF = os.path.join(settings.BASE_DIR.parent, "samples", "유상AS 견적서 샘플.pdf")


def quote_rows(*items, quote_no="NTK-991231-0001", day="2026-09-01"):
    """가상 견적서 행. items: (견적서 품명, 단가, 수량, 금액, 부품명)"""
    return [{"row_no": i, "sheet": "1쪽", "values": {
        "quote_no": quote_no, "effective_date": day, "quote_item": item, "part_name": part,
        "unit_price": f"{price:,}", "quantity": str(qty), "amount": f"{amount:,}",
        "quote_company": "가상산업", "quote_project": "가상 밸브 점검", "quote_note": "원거리 출장"}}
        for i, (item, price, qty, amount, part) in enumerate(items, start=1)]


class QuotePdfLayoutTests(APITestCase):
    """양식 읽기: 항목 이름 오른쪽 값, 가운데 정렬 머리글 표 (가상 글자 위치)"""

    def page(self):
        w = lambda text, x0, x1, top: Word(text, x0, x1, top, top + 8)
        return FormPage([
            w("견적 번호", 62, 96, 120), w("NTK-991231-0001", 114, 192, 120), w("등록번호", 325, 353, 120),
            w("날       짜", 63, 96, 143), w("2026-09-01", 114, 164, 143),
            w("업  체  명", 63, 96, 165), w("가상산업", 114, 150, 165), w("주      소", 325, 352, 166),
            w("가상시 가상로 1", 366, 450, 166),
            w("사  업   명", 62, 97, 243), w("가상 정수장", 114, 170, 243), w("밸브 점검", 175, 210, 243),
            w("비       고", 63, 96, 266), w("야간 작업", 114, 160, 266),
            w("번호", 55, 70, 329), w("품명 및 규격", 208, 252, 329), w("수량", 390, 406, 329),
            w("단가(원)", 433, 463, 329), w("금액(원)", 501, 531, 329),
            w("1", 61, 65, 350), w("XX-01 가상 모터", 81, 205, 350), w("2", 396, 400, 350),
            w("100,000", 441, 476, 350), w("200,000", 509, 543, 350),
            w("2", 61, 65, 371), w("가상 보드 Assy", 81, 160, 371), w("1", 396, 400, 371),
            w("50,000", 445, 476, 371), w("50,000", 513, 543, 371),
            w("(두 번째 줄)", 81, 140, 381),  # 품명이 다음 줄로 넘어간 경우
            w("납       기", 63, 96, 604), w("공급가액", 433, 464, 604), w("250,000", 509, 543, 604),
            w("비", 58, 66, 703), w("원거리 출장", 140, 200, 700), w("고", 58, 66, 726), w("장비 추가", 140, 190, 715),
            w("『 가상 인증 문구 』", 107, 487, 764),
        ], 595, 842)

    def test_read_header_and_items(self):
        page = self.page()
        self.assertEqual(value_right_of(page, "견적번호"), "NTK-991231-0001")
        self.assertEqual(value_right_of(page, "날짜"), "2026-09-01")
        self.assertEqual(value_right_of(page, "업체명"), "가상산업")  # 오른쪽 '주소' 항목 전에서 멈춤
        self.assertEqual(value_right_of(page, "사업명"), "가상 정수장 밸브 점검")  # 여러 조각을 이어 붙임
        self.assertEqual(value_right_of(page, "비고"), "야간 작업")
        self.assertEqual(bottom_note(page), "원거리 출장\n장비 추가")  # 아래쪽 비고 칸, 인증 문구는 제외
        self.assertEqual(read_items(page), [
            {"item": "XX-01 가상 모터", "quantity": "2", "unit_price": "100,000", "amount": "200,000"},
            {"item": "가상 보드 Assy (두 번째 줄)", "quantity": "1", "unit_price": "50,000", "amount": "50,000"},
        ])


class QuoteUploadTests(APITestCase):
    def setUp(self):
        self.client.force_authenticate(User.objects.create_user(
            "svc_leader", password="x", role=User.Role.LEADER, view_teams=[S], edit_teams=[S]))

    def upload(self, rows):
        with mock.patch("uploads.handlers.quote_pdf.QuotePdfHandler.parse", return_value=(rows, 0)):
            return self.client.post("/api/uploads/", {"kind": "quote_pdf",
                                                      "file": SimpleUploadedFile("견적서.pdf", b"%PDF")}, format="multipart")

    def test_save_price_and_remember_part_name(self):
        res = self.upload(quote_rows(("XX-01 가상 모터", 100000, 2, 200000, "Motor")))
        part_col = next(c for c in res.data["columns"] if c["key"] == "part_name")
        self.assertIsInstance(part_col["suggestions"], list)  # 직접 입력하면서 고르는 추천 목록
        self.assertEqual(self.client.post(f"/api/uploads/{res.data['id']}/confirm/").data["saved_count"], 1)
        price = PartPrice.objects.get()
        self.assertEqual((price.part_name, price.unit_price, price.effective_date, price.source, price.quote_no),
                         ("Motor", 100000, date(2026, 9, 1), "quote", "NTK-991231-0001"))
        self.assertEqual(QuotePartAlias.objects.get(quote_item="XX-01 가상 모터").part_name, "Motor")
        # 단가 화면에 출처와 함께 업체·사업명·비고 표시 (단가가 달라진 이유 참고)
        history = self.client.get("/api/service/part-prices/").data["parts"][0]["history"][0]
        self.assertEqual((history["source"], history["company"], history["project"], history["note"]),
                         ("견적서 NTK-991231-0001", "가상산업", "가상 밸브 점검", "원거리 출장"))

    def test_same_quote_twice_is_skipped(self):
        res = self.upload(quote_rows(("XX-01 가상 모터", 100000, 1, 100000, "Motor")))
        self.client.post(f"/api/uploads/{res.data['id']}/confirm/")
        again = self.upload(quote_rows(("XX-01 가상 모터", 100000, 1, 100000, "Motor")))
        self.assertEqual(again.data["summary"]["duplicate_rows"], 1)
        self.assertFalse(again.data["allow_duplicate_override"])  # 견적 번호가 기준이라 '중복 아님' 없음

    def test_validation(self):
        PartPrice.objects.create(part_name="Main Board", unit_price=1, effective_date=date(2026, 9, 1))
        res = self.upload(quote_rows(
            ("가상 품명A", 100000, 2, 150000, "Motor"),       # 수량 × 단가 ≠ 금액
            ("가상 품명B", 50000, 1, 50000, ""),               # 부품명 없음
            ("가상 품명C", 70000, 1, 70000, "Main Board"),     # 같은 날짜 단가가 이미 있음
            ("가상 품명D", 80000, 1, 80000, "Motor"),          # 파일 안에서 Motor·같은 날짜가 두 번
        ))
        errors = [r["errors"] for r in res.data["rows"]]
        self.assertIn("amount", errors[0])
        self.assertIn("part_name", errors[1])
        self.assertIn("이미 있습니다", errors[2]["part_name"])
        self.assertIn("1번째 줄", errors[3]["part_name"])

    def test_alias_fills_part_name_on_next_upload(self):
        QuotePartAlias.objects.create(quote_item="XX-01 가상 모터", part_name="Motor")
        handler = HANDLERS["quote_pdf"]
        with mock.patch("uploads.handlers.quote_pdf.read_pages", return_value=[QuotePdfLayoutTests().page()]):
            rows, _ = handler.parse(None)
        self.assertEqual([r["values"]["part_name"] for r in rows], ["Motor", ""])
        self.assertEqual(rows[0]["values"]["quote_note"], "야간 작업\n원거리 출장\n장비 추가")  # 비고 두 칸을 합침

    def test_member_cannot_upload(self):
        self.client.force_authenticate(User.objects.create_user(
            "svc_member", password="x", role=User.Role.MEMBER, view_teams=[S]))
        self.assertEqual(self.upload(quote_rows(("가상", 1, 1, 1, "Motor"))).status_code, 403)


@unittest.skipUnless(os.path.exists(QUOTE_SAMPLE_PDF), "실제 견적서 샘플이 없는 PC에서는 건너뜀 (samples/는 Git 제외)")
class RealSampleQuoteTests(APITestCase):
    """실제 샘플 읽기 확인. 실제 기업 값은 코드에 적지 않고 형식만 확인한다 (CLAUDE.md 7절)."""

    def test_parse_real_sample(self):
        handler = HANDLERS["quote_pdf"]
        with open(QUOTE_SAMPLE_PDF, "rb") as f:
            rows, _ = handler.parse(f)
        self.assertGreaterEqual(len(rows), 1)
        for row in rows:
            v = row["values"]
            self.assertRegex(v["quote_no"], r"^NTK-\d{6}-\d{4}$")
            self.assertRegex(v["effective_date"], r"^\d{4}-\d{2}-\d{2}$")
            self.assertTrue(v["quote_item"])
            self.assertTrue(v["quote_company"] and v["quote_project"])  # 업체명·사업명 읽힘
            # 부품명만 고르면 오류 없음 (수량 × 단가 = 금액 확인 포함)
            self.assertEqual(handler.validate({**v, "part_name": "가상 부품"}), {})
