from datetime import date
from io import BytesIO
from unittest.mock import patch

from openpyxl import load_workbook
from rest_framework.test import APITestCase

from accounts.models import User

from .audit import AuditForbiddenFieldError, record_audit
from .models import AuditLog, ExpenseCategory, LedgerEntry, MonthlyFinance, OtherExpense
from .rules import CLOSED, CURRENT, FUTURE, month_state

M = User.Team.MANAGEMENT
P = User.Team.PRODUCTION
TODAY = date(2026, 11, 4)

VALUES = {
    "product_sales": 100,
    "merchandise_sales": 20,
    "service_sales": 10,
    "merchandise_purchase": 14,
    "material_purchase": 40,
    "expense": 30,
}


def make_user(username, role, view=(), edit=()):
    return User.objects.create_user(username=username, password="x", role=role, view_teams=list(view), edit_teams=list(edit))


class MonthStateTests(APITestCase):
    def test_states(self):
        self.assertEqual(month_state(2026, 12, TODAY), FUTURE)
        self.assertEqual(month_state(2026, 11, TODAY), CURRENT)
        self.assertEqual(month_state(2026, 10, TODAY), CLOSED)
        self.assertEqual(month_state(2025, 12, TODAY), CLOSED)


class AuditTests(APITestCase):
    def test_forbidden_field_rejected(self):
        user = make_user("mgmt", User.Role.MEMBER, [M])
        with self.assertRaises(AuditForbiddenFieldError):
            record_audit(actor=user, screen="entry", action="CONFIRM", target_type="X", target_id=1,
                         target_label="x", meta={"api_token": "abc"})

    def test_log_cannot_be_changed(self):
        user = make_user("mgmt", User.Role.MEMBER, [M])
        log = record_audit(actor=user, screen="entry", action="CONFIRM", target_type="X", target_id=1, target_label="x")
        with self.assertRaises(ValueError):
            log.save()
        with self.assertRaises(ValueError):
            log.delete()


class EntryTestCase(APITestCase):
    def setUp(self):
        self.mgmt = make_user("mgmt", User.Role.MEMBER, [M])
        self.ad = ExpenseCategory.objects.create(name="광고선전비", sort_order=1)
        self.old = ExpenseCategory.objects.create(name="옛 항목", sort_order=2, is_active=False)
        self.client.force_authenticate(self.mgmt)

    def stamp(self, month):
        """화면이 불러온 updated_at (처음이면 None)"""
        return self.client.get(f"/api/management/monthly/2026/{month}/").data["updated_at"]

    def put(self, month, intent, others=(), cash=None, values=VALUES, stamp="load"):
        body = {
            "intent": intent,
            "values": values,
            "other_expenses": list(others),
            "cash_balance": cash,
            "expected_updated_at": self.stamp(month) if stamp == "load" else stamp,
        }
        return self.client.put(f"/api/management/monthly/2026/{month}/", body, format="json")

    def unconfirm(self, month):
        return self.client.post(
            f"/api/management/monthly/2026/{month}/unconfirm/", {"expected_updated_at": self.stamp(month)}, format="json"
        )


@patch("management.views.timezone.localdate", return_value=TODAY)
class MonthlyEntryApiTests(EntryTestCase):
    def test_new_month_is_empty(self, _):
        res = self.client.get("/api/management/monthly/2026/10/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "new")
        self.assertEqual(res.data["values"]["product_sales"], 0)
        # 비활성 항목은 금액이 없으면 보이지 않음
        self.assertEqual([e["name"] for e in res.data["other_expenses"]], ["광고선전비"])
        self.assertTrue(res.data["abilities"]["can_confirm"])

    def test_draft_then_confirm(self, _):
        res = self.put(10, "draft", [{"category_id": self.ad.id, "amount": 5}], cash=777)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "draft")
        self.assertEqual(res.data["cash_balance"], 777)
        res = self.put(10, "confirm", [{"category_id": self.ad.id, "amount": 6}])
        self.assertEqual(res.data["status"], "confirmed")
        f = MonthlyFinance.objects.get(year=2026, month=10)
        self.assertIsNotNone(f.confirmed_at)
        self.assertIsNone(f.cash_balance)  # 비우면 null
        self.assertEqual(OtherExpense.objects.get(monthly=f).amount, 6)

    def test_current_month_draft_only(self, _):
        self.assertEqual(self.put(11, "draft").status_code, 200)
        self.assertEqual(self.put(11, "confirm").status_code, 403)

    def test_future_month_blocked(self, _):
        self.assertEqual(self.put(12, "draft").status_code, 403)

    def test_confirmed_month_needs_update_intent(self, _):
        self.put(10, "confirm")
        self.assertEqual(self.put(10, "draft").status_code, 403)
        self.assertEqual(self.put(10, "update_confirmed").status_code, 200)

    def test_unconfirm(self, _):
        self.put(10, "confirm")
        res = self.unconfirm(10)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "draft")
        self.assertIsNone(MonthlyFinance.objects.get(year=2026, month=10).confirmed_at)

    def test_inactive_category_rejected(self, _):
        res = self.put(10, "draft", [{"category_id": self.old.id, "amount": 5}])
        self.assertEqual(res.status_code, 400)

    def test_negative_amount_rejected(self, _):
        res = self.put(10, "draft", values={**VALUES, "expense": -1})
        self.assertEqual(res.status_code, 400)

    def test_previous_month_values(self, _):
        self.put(9, "confirm")
        res = self.client.get("/api/management/monthly/2026/10/")
        self.assertEqual(res.data["previous"]["values"]["product_sales"], 100)

    def test_other_teams_blocked(self, _):
        leader = make_user("prod", User.Role.LEADER, [P], [P])
        self.client.force_authenticate(leader)
        self.assertEqual(self.client.get("/api/management/monthly/2026/10/").status_code, 403)
        self.assertEqual(self.put(10, "draft", stamp=None).status_code, 403)
        self.assertEqual(self.client.get("/api/management/history/").status_code, 403)
        self.assertEqual(self.client.get("/api/management/monthly/export/?year=2026&period=month&month=10").status_code, 403)


@patch("management.views.timezone.localdate", return_value=TODAY)
class ConcurrencyTests(EntryTestCase):
    """동시 수정 확인: 불러온 뒤 다른 사람이 먼저 저장했으면 409"""

    def test_stale_save_rejected(self, _):
        stale = self.stamp(10)  # 두 사람이 같은 화면(새 달)을 열었다
        self.assertEqual(self.put(10, "draft", stamp=stale).status_code, 200)  # 한 사람이 먼저 저장
        res = self.put(10, "draft", values={**VALUES, "expense": 99}, stamp=stale)
        self.assertEqual(res.status_code, 409)
        self.assertEqual(MonthlyFinance.objects.get(year=2026, month=10).expense, 30)  # 덮어쓰지 않음

    def test_stale_unconfirm_rejected(self, _):
        self.put(10, "confirm")
        stale = self.stamp(10)
        self.put(10, "update_confirmed", values={**VALUES, "expense": 1})
        res = self.client.post("/api/management/monthly/2026/10/unconfirm/", {"expected_updated_at": stale}, format="json")
        self.assertEqual(res.status_code, 409)


@patch("management.views.timezone.localdate", return_value=TODAY)
class EntryAuditTests(EntryTestCase):
    def test_draft_not_recorded_confirm_recorded(self, _):
        self.put(10, "draft")
        self.assertEqual(AuditLog.objects.count(), 0)
        self.put(10, "confirm", values={**VALUES, "expense": 31})
        log = AuditLog.objects.get()
        self.assertEqual((log.action, log.screen, log.actor_username), ("CONFIRM", "entry", "mgmt"))
        self.assertEqual(log.target_label, "2026년 10월 월간 입력")
        self.assertIn({"field": "status", "label": "상태", "before": "임시저장", "after": "확정"}, log.changes)
        self.assertIn({"field": "expense", "label": "경비 지출액", "before": "30원", "after": "31원"}, log.changes)

    def test_update_confirmed_records_only_changes(self, _):
        self.put(10, "confirm", [{"category_id": self.ad.id, "amount": 5}])
        self.put(10, "update_confirmed", [{"category_id": self.ad.id, "amount": 5}])  # 바뀐 칸 없음 → 기록 안 함
        self.assertEqual(AuditLog.objects.count(), 1)
        self.put(10, "update_confirmed", [{"category_id": self.ad.id, "amount": 8}])
        log = AuditLog.objects.first()
        self.assertEqual(log.action, "UPDATE_CONFIRMED")
        self.assertEqual(log.changes, [{"field": "other_expense", "label": "그 외 지출 · 광고선전비", "before": "5원", "after": "8원"}])

    def test_unconfirm_recorded_and_history_api(self, _):
        self.put(10, "confirm")
        self.unconfirm(10)
        res = self.client.get("/api/management/history/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["total"], 2)
        self.assertEqual(res.data["rows"][0]["action"], "확정 취소")
        self.assertEqual(res.data["rows"][0]["lines"], ["상태: 확정 → 임시저장"])
        self.assertEqual(self.client.get("/api/management/history/?action=CONFIRM").data["total"], 1)
        self.assertEqual(self.client.get("/api/management/history/?q=9월").data["total"], 0)


@patch("management.views.timezone.localdate", return_value=TODAY)
class LedgerTests(EntryTestCase):
    def test_rows_without_ar_and_hidden(self, _):
        LedgerEntry.objects.create(year=2026, month=10, kind="ap", purchase_type="goods", partner_name="가", amount=110)
        LedgerEntry.objects.create(year=2026, month=10, kind="ar", partner_name="나", amount=1)
        LedgerEntry.objects.create(year=2026, month=10, kind="accrued_staff", partner_name="다", amount=5, deleted_at="2026-10-31T00:00:00Z")
        LedgerEntry.objects.create(year=2026, month=9, kind="ap", partner_name="라", amount=7)
        res = self.client.get("/api/management/monthly/2026/10/ledger/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["rows"], [{"kind": "ap", "amount": 110, "purchase_type": "goods", "expense_type": None, "auto_transfer": False}])

    def test_read_only_month_blocked(self, _):
        self.assertEqual(self.client.get("/api/management/monthly/2026/12/ledger/").status_code, 403)


@patch("management.export.timezone.localdate", return_value=TODAY)
@patch("management.views.timezone.localdate", return_value=TODAY)
class ExportTests(EntryTestCase):
    def download(self, query):
        res = self.client.get(f"/api/management/monthly/export/?{query}")
        self.assertEqual(res.status_code, 200)
        return res, load_workbook(BytesIO(res.content))

    def test_quarter_total_only_confirmed(self, *_):
        self.put(7, "confirm", [{"category_id": self.ad.id, "amount": 5}])
        self.put(8, "draft")
        res, wb = self.download("year=2026&period=quarter&quarter=3")
        self.assertIn("2026-Q3.xlsx", res["Content-Disposition"])
        self.assertEqual(wb.sheetnames, ["2026-Q3", "2026-07", "2026-08"])  # 합계 + 데이터가 있는 달
        total = wb["2026-Q3"]
        cells = {total.cell(r, 3).value: total.cell(r, 4).value for r in range(1, total.max_row + 1)}
        self.assertEqual(cells["상품 매입액"], 14)  # 확정된 7월만
        self.assertEqual(cells["광고선전비"], 5)
        self.assertEqual(total["H1"].value, "집계: 확정된 달만 (7월)")
        self.assertEqual(total["H2"].value, "제외: 8월 임시저장 · 9월 입력 없음")
        log = AuditLog.objects.get(action="EXPORT")
        self.assertEqual(log.meta["sheet_count"], 3)

    def test_month_sheet_without_data(self, *_):
        _, wb = self.download("year=2026&period=month&month=10")
        ws = wb["2026-10"]
        self.assertEqual(ws["H1"].value, "상태: 입력 없음")
        self.assertEqual(ws["C3"].value, "월간 상품 매입액")
        self.assertEqual(ws["F3"].value, "=SUM(D3:D4)")

    def test_future_period_rejected(self, *_):
        res = self.client.get("/api/management/monthly/export/?year=2027&period=year")
        self.assertEqual(res.status_code, 400)
