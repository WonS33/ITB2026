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
        self.login(User.Role.MANAGEMENT, view=(), edit=())  # 경영지원팀: 전체 수정
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
    def test_parse_real_sample(self):
        from .handlers import HANDLERS

        with open(SAMPLE_PDF, "rb") as f:
            rows, _ = HANDLERS["sales_order_pdf"].parse(f)
        v = rows[0]["values"]
        self.assertEqual((v["sales_no"], v["due_date"], v["product_name"], v["quantity"]),
                         ("NTK-SO-260000", "2026-03-13", "제수 150A: NTI-03", "3"))
        self.assertEqual((v["industry"], v["order_doc_no"], v["flange"]), ("상하수도", "26024", "F10A"))


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
