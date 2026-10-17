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
