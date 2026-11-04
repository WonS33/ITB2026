import json
from datetime import date
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from openpyxl import load_workbook
from rest_framework.test import APITestCase

from accounts.models import User

from .audit import AuditForbiddenFieldError, record_audit
from .models import AnnualSalesTarget, AuditLog, ExpenseCategory, LedgerEntry, MonthlyFinance, OtherExpense, Receivable
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


class AllocationTests(APITestCase):
    """분기·월 목표 배분 (조원 저장소 targets.ts 규칙)"""

    def test_empty_quarters_split_with_rest_on_last(self):
        from .targets import allocate_month_targets, allocate_quarter_targets

        r = allocate_quarter_targets(1000, [None, None, None, None])
        self.assertEqual(r["quarters"], [250, 250, 250, 250])
        r = allocate_quarter_targets(1001, [None, 300, None, None])
        self.assertEqual(r["quarters"], [233, 300, 233, 235])  # 701 ÷ 3, 나머지 2원은 마지막 빈 분기
        self.assertEqual(r["sources"], ["allocated", "input", "allocated", "allocated"])
        self.assertIsNone(r["warning"])
        self.assertEqual(allocate_month_targets([10, 0, 0, 0])[:3], [3, 3, 4])

    def test_warnings(self):
        from .targets import allocate_quarter_targets

        self.assertEqual(allocate_quarter_targets(100, [50, 50, 50, None])["warning"], "QUARTER_SUM_EXCEEDS_ANNUAL")
        self.assertEqual(allocate_quarter_targets(100, [20, 20, 20, 20])["warning"], "QUARTER_SUM_MISMATCH")


class TargetApiTests(APITestCase):
    def setUp(self):
        self.client.force_authenticate(make_user("mgmt", User.Role.MEMBER, [M]))

    def put(self, amount, quarters=(None, None, None, None), headcount=None, stamp="load"):
        if stamp == "load":
            stamp = self.client.get("/api/management/targets/2026/").data["updated_at"]
        body = {"target_amount": amount, "quarters": list(quarters), "headcount": headcount, "expected_updated_at": stamp}
        return self.client.put("/api/management/targets/2026/", body, format="json")

    def test_create_then_update_recorded(self):
        res = self.put(1000, headcount=12)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["allocation"]["quarters"], [250, 250, 250, 250])
        log = AuditLog.objects.get()
        self.assertEqual((log.action, log.target_label), ("CREATE", "2026년 목표"))
        self.put(1000, quarters=(400, None, None, None), headcount=12)
        log = AuditLog.objects.first()
        self.assertEqual(log.action, "UPDATE")
        self.assertEqual(log.changes, [{"field": "q1_target", "label": "1분기 목표", "before": "자동 배분", "after": "400원"}])
        self.put(1000, quarters=(400, None, None, None), headcount=12)  # 바뀐 칸 없음 → 기록 안 함
        self.assertEqual(AuditLog.objects.count(), 2)

    def test_zero_target_rejected(self):
        self.assertEqual(self.put(0).status_code, 400)

    def test_stale_save_rejected(self):
        self.put(1000)
        self.assertEqual(self.put(2000, stamp=None).status_code, 409)  # 처음 불러올 때는 없던 목표

    def test_other_team_blocked(self):
        self.client.force_authenticate(make_user("prod", User.Role.LEADER, [P], [P]))
        self.assertEqual(self.client.get("/api/management/targets/2026/").status_code, 403)


class ExpenseCategoryApiTests(APITestCase):
    def setUp(self):
        self.client.force_authenticate(make_user("mgmt", User.Role.MEMBER, [M]))
        self.a = ExpenseCategory.objects.create(name="광고선전비", sort_order=1)
        self.b = ExpenseCategory.objects.create(name="접대비", sort_order=2)

    def save(self, items, deleted=(), version=None):
        version = version or self.client.get("/api/management/expense-categories/").data["version"]
        body = {"items": items, "deleted_ids": list(deleted), "version": version}
        return self.client.put("/api/management/expense-categories/", body, format="json")

    def item(self, c, **kw):
        return {"id": c.id if c else None, "name": c.name if c else "", "cost_type": "", "is_active": True, **kw}

    def test_swap_names_add_and_reorder(self):
        res = self.save([self.item(self.b, name="광고선전비"), self.item(self.a, name="접대비"), self.item(None, name="  연구  개발비 ")])
        self.assertEqual(res.status_code, 200)
        self.assertEqual([r["name"] for r in res.data["rows"]], ["광고선전비", "접대비", "연구 개발비"])
        actions = sorted(AuditLog.objects.values_list("action", flat=True))
        self.assertEqual(actions, ["CREATE", "UPDATE", "UPDATE", "UPDATE"])  # 이름 2개 + 순서 1건 + 추가

    def test_duplicate_name_rejected(self):
        res = self.save([self.item(self.a), self.item(self.b, name="광고선전비")])
        self.assertEqual(res.status_code, 400)

    def test_used_category_cannot_be_deleted(self):
        f = MonthlyFinance.objects.create(year=2026, month=9)
        OtherExpense.objects.create(monthly=f, category=self.a, amount=5)
        self.assertEqual(self.save([self.item(self.b)], deleted=[self.a.id]).status_code, 400)
        res = self.save([self.item(self.a)], deleted=[self.b.id])
        self.assertEqual(res.status_code, 200)
        self.assertFalse(ExpenseCategory.objects.filter(pk=self.b.pk).exists())

    def test_stale_version_rejected(self):
        old = self.client.get("/api/management/expense-categories/").data["version"]
        self.save([self.item(self.a, is_active=False), self.item(self.b)])
        self.assertEqual(self.save([self.item(self.a), self.item(self.b)], version=old).status_code, 409)

    def test_missing_row_is_conflict(self):
        # 그 사이 다른 사람이 항목을 추가했으면 화면 목록에 없는 항목이 생김
        self.assertEqual(self.save([self.item(self.a)]).status_code, 409)


def finance(year, month, status="confirmed", product=100, merch=0, service=0, purchase=0, material=0, expense=0):
    return MonthlyFinance.objects.create(
        year=year, month=month, status=status, product_sales=product, merchandise_sales=merch,
        service_sales=service, merchandise_purchase=purchase, material_purchase=material, expense=expense,
    )


class MetricsTests(APITestCase):
    """경영지원 지표 (조원 저장소 metrics 규칙)"""

    def summary(self, kind, year=2026, **kw):
        from common.periods import make_period

        from .metrics import management_summary

        return management_summary(make_period(kind, year, **kw), TODAY)

    def test_only_confirmed_months_and_profit(self):
        finance(2026, 7, product=200, merch=100, purchase=50, expense=30)
        finance(2026, 8, status="draft", product=999)
        ad = ExpenseCategory.objects.create(name="광고선전비")
        OtherExpense.objects.create(monthly=MonthlyFinance.objects.get(month=7), category=ad, amount=20)
        s = self.summary("quarter", quarter=3)
        self.assertEqual(s["revenue"]["total"], 300)  # 8월(임시저장)은 빠짐
        self.assertEqual(s["costs"]["total"], 100)  # 매입 50 + 경비 30 + 그 외 20
        self.assertEqual(s["profit"], {"amount": 200, "margin": 66.7})
        c = s["confirmation"]
        self.assertEqual(c["unconfirmed_months"], [{"year": 2026, "month": 8, "reason": "draft"}, {"year": 2026, "month": 9, "reason": "missing"}])
        self.assertTrue(c["is_partial"])

    def test_aligned_comparison(self):
        # 3분기는 7월만 확정 → 2분기도 첫 달(4월)끼리만 비교
        finance(2026, 7, product=150)
        finance(2026, 4, product=100)
        finance(2026, 5, product=500)
        s = self.summary("quarter", quarter=3)
        prev = s["changes"]["previous"]
        self.assertEqual(prev["aligned"]["base"], [{"year": 2026, "month": 4}])
        self.assertEqual(prev["revenue"]["rate"], 50.0)
        self.assertEqual(s["changes"]["last_year"]["revenue"], {"rate": None, "reason": "no-data"})

    def test_no_current_data_is_not_minus_100(self):
        finance(2026, 6, product=100)
        s = self.summary("quarter", quarter=3)
        self.assertEqual(s["changes"]["previous"]["revenue"]["reason"], "no-current-data")

    def test_targets_and_annual_progress(self):
        AnnualSalesTarget.objects.create(year=2026, target_amount=1200)  # 분기 300, 월 100
        for m in range(1, 7):
            finance(2026, m, product=100)
        finance(2026, 7, product=50)  # 3분기는 7월만
        finance(2026, 8, status="draft")
        s = self.summary("month", month=7)
        t = s["targets"]
        self.assertEqual(t["period"], {"kind": "quarter-progress", "target": 300, "actual": 50, "rate": 16.7})
        self.assertEqual(t["month"]["rate"], 50.0)  # 7월 목표 100 대비 50
        q = {x["quarter"]: x for x in t["quarters"]}
        self.assertEqual((q[1]["rate"], q[1]["state"], q[1]["warn"]), (100.0, "ended", False))
        self.assertEqual(q[3]["unconfirmed_months"], [8, 9])  # 끝난 분기인데 미확정
        self.assertFalse(q[3]["warn"])  # 미확정 달이 있으면 빨강 대신 안내
        self.assertEqual(q[4]["state"], "current")
        a = t["annual"]
        self.assertEqual((a["actual"], a["basis_month"], a["elapsed"]), (650, 7, 58.3))
        self.assertEqual(a["excluded_months"], [8, 9, 10])

    def test_no_target(self):
        self.assertIsNone(self.summary("year")["targets"])

    def test_trend_statuses(self):
        finance(2026, 9, product=10)
        finance(2026, 10, status="draft", product=20)
        points = self.summary("quarter", quarter=4)["trend"]
        self.assertEqual(len(points), 12)
        by = {(p["year"], p["month"]): p for p in points}
        self.assertEqual(by[(2026, 9)]["status"], "confirmed")
        self.assertEqual(by[(2026, 10)]["revenue"], 20)  # 임시저장도 값은 보이되 status로 구분
        self.assertEqual(by[(2026, 11)]["status"], "pending")
        self.assertEqual(by[(2026, 1)]["status"], "missing")

    def test_receivables_last_month_with_entries(self):
        AR = LedgerEntry.Kind.AR
        LedgerEntry.objects.create(year=2026, month=9, kind=AR, ar_status="long_overdue", partner_name="가", amount=100)
        LedgerEntry.objects.create(year=2026, month=10, kind=AR, ar_status="long_overdue", partner_name="가", amount=70)
        LedgerEntry.objects.create(year=2026, month=10, kind=AR, ar_status="scheduled", partner_name="나", amount=30)
        LedgerEntry.objects.create(year=2026, month=10, kind=AR, ar_status="collected", partner_name="다", amount=5)
        r = self.summary("quarter", quarter=4)["receivables"]
        self.assertEqual((r["month"], r["total"], r["customer_count"]), ({"year": 2026, "month": 10}, 100, 2))
        self.assertEqual(r["collected"]["amount"], 5)  # 당월 수금은 미수에 넣지 않음
        self.assertIsNone(self.summary("quarter", quarter=2)["receivables"]["month"])


@patch("management.dashboard_views.timezone.localdate", return_value=TODAY)
class DashboardApiTests(APITestCase):
    def test_dashboard_and_permissions(self, _):
        self.client.force_authenticate(make_user("mgmt", User.Role.MEMBER, [M]))
        res = self.client.get("/api/management/dashboard/?year=2026&period=quarter&quarter=3")
        self.assertEqual(res.status_code, 200)
        self.assertIn("production", res.data["teams"])
        self.assertIn("service", res.data["teams"])
        self.client.force_authenticate(make_user("prod", User.Role.LEADER, [P], [P]))
        self.assertEqual(self.client.get("/api/management/dashboard/").status_code, 403)

    def test_targets_export(self, _):
        self.client.force_authenticate(make_user("mgmt", User.Role.MEMBER, [M]))
        AnnualSalesTarget.objects.create(year=2026, target_amount=1200, q4_target=600)
        finance(2026, 1, product=100)
        finance(2026, 2, status="draft")
        res = self.client.get("/api/management/targets/2026/export/")
        self.assertEqual(res.status_code, 200)
        ws = load_workbook(BytesIO(res.content))["2026"]
        cells = {(r, c): ws.cell(r, c).value for r in range(1, ws.max_row + 1) for c in range(1, 10)}
        self.assertIn("자동 배분", cells.values())
        self.assertIn("임시저장 — 합계 제외", cells.values())
        self.assertTrue(any(str(v).startswith("← 1분기 (2·3월 미확정") or str(v).startswith("← 1분기 달성률") for v in cells.values()))
        self.assertEqual(AuditLog.objects.get().screen, "targets-export")


@patch("management.receivables_views.timezone.localdate", return_value=TODAY)
class ReceivableApiTests(APITestCase):
    """미수금 건별 기록 (조원 저장소 receivables 규칙)"""

    def setUp(self):
        self.client.force_authenticate(make_user("mgmt", User.Role.MEMBER, [M]))

    def create(self, **kw):
        body = {"customer_name": "  가나   상사 ", "occurred_on": "2026-07-01", "amount": 1000, "due_on": "2026-08-01", "note": "", **kw}
        return self.client.post("/api/management/receivables/", body, format="json")

    def row(self, pk):
        rows = self.client.get("/api/management/receivables/").data["rows"]
        return next(r for r in rows if r["id"] == pk)

    def act(self, pk, action, **kw):
        body = {"expected_updated_at": self.row(pk)["updated_at"], **kw}
        return self.client.post(f"/api/management/receivables/{pk}/{action}/", body, format="json")

    def test_create_status_and_audit(self, _):
        self.assertEqual(self.create().status_code, 201)
        r = Receivable.objects.get()
        self.assertEqual(r.customer_name, "가나 상사")  # 공백 정리
        row = self.row(r.pk)
        self.assertEqual((row["age_days"], row["over90"], row["overdue"]), (126, True, True))
        log = AuditLog.objects.get()
        self.assertEqual((log.screen, log.action, log.target_label), ("receivables", "CREATE", "가나 상사 · 2026-07-01 발생"))

    def test_date_rules(self, _):
        self.assertEqual(self.create(occurred_on="2026-12-01").status_code, 400)  # 미래 발생일
        self.assertEqual(self.create(due_on="2026-06-01").status_code, 400)  # 예정일 < 발생일
        self.assertEqual(self.create(amount=0).status_code, 400)

    def test_collect_uncollect_hide_restore(self, _):
        self.create()
        pk = Receivable.objects.get().pk
        self.assertEqual(self.act(pk, "collect", collected_on="2026-12-01").status_code, 400)  # 미래 수금일
        self.assertEqual(self.act(pk, "collect", collected_on="2026-10-01").status_code, 200)
        self.assertTrue(Receivable.objects.get().is_collected)
        self.assertEqual(self.act(pk, "collect", collected_on="2026-10-01").status_code, 400)  # 이미 수금
        self.assertEqual(self.act(pk, "uncollect").status_code, 200)
        self.assertEqual(self.act(pk, "hide").status_code, 200)
        self.assertEqual(self.act(pk, "collect", collected_on="2026-10-01").status_code, 400)  # 숨긴 건
        self.assertEqual(self.act(pk, "restore").status_code, 200)
        actions = list(AuditLog.objects.order_by("id").values_list("action", flat=True))
        self.assertEqual(actions, ["CREATE", "COLLECT", "UNCOLLECT", "HIDE", "RESTORE"])
        history = self.client.get(f"/api/management/history/row/?type=Receivable&id={pk}").data["rows"]
        self.assertEqual(history[-1]["action"], "추가")
        self.assertEqual(history[-2]["lines"], ["상태: 미수 → 수금 완료", "수금일: (없음) → 2026-10-01"])

    def test_update_and_conflict(self, _):
        self.create()
        pk = Receivable.objects.get().pk
        stale = self.row(pk)["updated_at"]
        body = {"customer_name": "가나 상사", "occurred_on": "2026-07-01", "amount": 2000, "due_on": None, "note": "",
                "expected_updated_at": stale}
        self.assertEqual(self.client.put(f"/api/management/receivables/{pk}/", body, format="json").status_code, 200)
        self.assertEqual(self.client.put(f"/api/management/receivables/{pk}/", body, format="json").status_code, 409)
        # 미수 건에 수금일을 보내면 거부
        body = {**body, "expected_updated_at": self.row(pk)["updated_at"], "collected_on": "2026-10-01"}
        self.assertEqual(self.client.put(f"/api/management/receivables/{pk}/", body, format="json").status_code, 400)

    def test_basis_and_export(self, _):
        self.create(amount=500)
        LedgerEntry.objects.create(year=2026, month=10, kind="ar", ar_status="scheduled", partner_name="가", amount=300)
        basis = self.client.get("/api/management/receivables/").data["basis"]
        self.assertEqual((basis["ar_total"], basis["item_total"], str(basis["as_of"])), (300, 500, "2026-10-31"))
        with patch("management.receivables_views.timezone.localdate", return_value=TODAY):
            res = self.client.get("/api/management/receivables/export/?year=2026&period=quarter&quarter=3")
        self.assertEqual(res.status_code, 200)
        wb = load_workbook(BytesIO(res.content))
        self.assertEqual(wb.sheetnames, ["미수금 통계", "미수금 상세"])
        self.assertEqual(wb["미수금 통계"]["C1"].value, "미수금 통계 (9/30 기준)")
        self.assertEqual(wb["미수금 상세"]["A2"].value, "가나 상사")

    def test_other_team_blocked(self, _):
        self.client.force_authenticate(make_user("svc", User.Role.LEADER, [User.Team.SERVICE], [User.Team.SERVICE]))
        self.assertEqual(self.client.get("/api/management/receivables/").status_code, 403)
        self.assertEqual(self.create().status_code, 403)


class ItemReceivableTests(APITestCase):
    def test_outstanding_at_date_and_buckets(self):
        from .receivables import item_receivables

        Receivable.objects.create(customer_name="가", occurred_on=date(2026, 1, 1), amount=100, is_collected=True, collected_on=date(2026, 3, 1))
        Receivable.objects.create(customer_name="나", occurred_on=date(2026, 2, 20), amount=50)
        Receivable.objects.create(customer_name="다", occurred_on=date(2026, 2, 1), amount=7, deleted_at="2026-02-02T00:00:00Z")
        r = item_receivables(date(2026, 2, 28))  # 2월 말에는 가(3월 수금)도 아직 미수
        self.assertEqual((r["total"], r["count"]), (150, 2))
        self.assertEqual({i["customer_name"]: i["bucket"] for i in r["items"]}, {"가": "31-60", "나": "0-30"})
        self.assertEqual(item_receivables(date(2026, 3, 31))["total"], 50)


@patch("management.ledger_views.timezone.localdate", return_value=TODAY)
class LedgerApiTests(APITestCase):
    """경영지원 관리 장부 (조원 저장소 ledger 규칙)"""

    def setUp(self):
        self.client.force_authenticate(make_user("mgmt", User.Role.MEMBER, [M]))

    def add(self, month=10, **fields):
        body = {"year": 2026, "month": month, "fields": {"kind": "ar", "ar_status": "scheduled", "partner_name": "가나", "amount": 1100, **fields}}
        return self.client.post("/api/management/ledger/", body, format="json")

    def rows(self, month=10):
        return self.client.get(f"/api/management/ledger/?year=2026&month={month}").data["rows"]

    def test_add_rules(self, _):
        self.assertEqual(self.add().status_code, 201)
        self.assertEqual(self.add(month=12).status_code, 400)  # 미래 달
        self.assertEqual(self.add(ar_status="").status_code, 400)  # 상태 필수
        self.assertEqual(self.add(partner_code="123").status_code, 400)  # 코드 10자리
        self.assertEqual(self.add(ar_status="collected").status_code, 400)  # 당월 수금은 완료일 필수
        self.assertEqual(self.add(ar_status="scheduled", settled_on="2026-10-01").status_code, 400)  # 수금예정에는 완료일 없음
        self.assertEqual(self.add(kind="ap", purchase_type="").status_code, 400)
        res = self.add(kind="accrued_vendor", expense_type="other", auto_transfer=True, ar_status="long_overdue", partner_code="0000000087")
        self.assertEqual(res.status_code, 201)
        e = LedgerEntry.objects.get(kind="accrued_vendor")
        self.assertEqual((e.ar_status, e.partner_code, e.auto_transfer), ("", "", True))  # 구분에 안 맞는 칸은 비움
        log = AuditLog.objects.filter(action="CREATE").order_by("id").last()
        self.assertEqual(log.target_label, "2026-10 미지급비용-업체 · 가나")

    def test_update_hide_restore_and_conflict(self, _):
        self.add(partner_code="0000000087")
        row = self.rows()[0]
        body = {"expected_updated_at": row["updated_at"], "fields": {"kind": "ar", "ar_status": "collected", "partner_name": "가나", "amount": 1100,
                                                                     "partner_code": "0000000087", "settled_on": "2026-10-20"}}
        self.assertEqual(self.client.put(f"/api/management/ledger/{row['id']}/", body, format="json").status_code, 200)
        self.assertEqual(self.client.put(f"/api/management/ledger/{row['id']}/", body, format="json").status_code, 409)  # 옛 시각
        log = AuditLog.objects.filter(action="UPDATE").get()
        self.assertIn({"field": "ar_status", "label": "상태", "before": "당월 수금예정", "after": "당월 수금"}, log.changes)
        self.assertIn({"field": "settled_on", "label": "수금 완료일", "before": None, "after": "2026-10-20"}, log.changes)
        # 구분은 바꿀 수 없음
        row = self.rows()[0]
        body = {"expected_updated_at": row["updated_at"], "fields": {"kind": "ap", "purchase_type": "goods", "partner_name": "가나", "amount": 1}}
        self.assertEqual(self.client.put(f"/api/management/ledger/{row['id']}/", body, format="json").status_code, 400)
        res = self.client.post(f"/api/management/ledger/{row['id']}/hide/", {"expected_updated_at": row["updated_at"]}, format="json")
        self.assertEqual(res.status_code, 200)
        row = self.rows()[0]
        self.assertTrue(row["hidden"])
        res = self.client.post(f"/api/management/ledger/{row['id']}/restore/", {"expected_updated_at": row["updated_at"]}, format="json")
        self.assertEqual(res.status_code, 200)
        history = self.client.get(f"/api/management/history/row/?type=LedgerEntry&id={row['id']}").data["rows"]
        self.assertEqual([h["action"] for h in history], ["복구", "숨김", "수정", "추가"])

    def test_copy_previous_month(self, _):
        self.add(month=9, ar_status="collected", settled_on="2026-09-20", partner_name="받음")
        self.add(month=9, ar_status="long_overdue", partner_name="장기", due_on="2026-12-31")
        self.add(month=9, kind="accrued_vendor", expense_type="other", auto_transfer=True, partner_name="통신")
        hidden = LedgerEntry.objects.create(year=2026, month=9, kind="ap", purchase_type="goods", partner_name="숨김", amount=1, deleted_at="2026-09-30T00:00:00Z")
        preview = self.client.get("/api/management/ledger/copy/?year=2026&month=10").data
        self.assertEqual((preview["from"], preview["existing"], preview["source_count"], preview["total"]), ("2026-09", 0, 3, 2))
        self.assertEqual(preview["collected"], {"count": 1, "amount": 1100})
        body = {"year": 2026, "month": 10, "include_collected": True, "expected_source_count": 3}
        self.assertEqual(self.client.post("/api/management/ledger/copy/", {**body, "expected_source_count": 2}, format="json").status_code, 409)
        self.assertEqual(self.client.post("/api/management/ledger/copy/", body, format="json").status_code, 200)
        copied = LedgerEntry.objects.filter(year=2026, month=10).order_by("created_at", "id")
        self.assertEqual([(e.partner_name, e.ar_status, e.settled_on) for e in copied],
                         [("받음", "scheduled", None), ("장기", "long_overdue", None), ("통신", "", None)])
        self.assertTrue(copied[2].auto_transfer)
        self.assertEqual(copied[1].due_on, date(2026, 12, 31))  # 예정일은 그대로
        self.assertNotIn(hidden.partner_name, [e.partner_name for e in copied])
        # 이번 달에 이미 행이 있으면 다시 불러올 수 없음
        self.assertEqual(self.client.post("/api/management/ledger/copy/", body, format="json").status_code, 409)
        log = AuditLog.objects.get(screen="ledger-copy")
        self.assertEqual(self.client.get("/api/management/history/?screen=ledger-copy").data["rows"][0]["lines"],
                         ["2026-09 → 2026-10 · 3행 저장 · 당월 수금 1행 포함"])
        self.assertEqual(log.meta["saved_rows"], 3)

    def test_other_team_blocked(self, _):
        self.client.force_authenticate(make_user("prod", User.Role.LEADER, [P], [P]))
        self.assertEqual(self.client.get("/api/management/ledger/").status_code, 403)
        self.assertEqual(self.add().status_code, 403)


TEST_FILES = Path(__file__).parent / "test_files"


@patch("management.ledger_views.timezone.localdate", return_value=TODAY)
@patch("management.ledger_import_views.timezone.localdate", return_value=TODAY)
class LedgerImportTests(APITestCase):
    """경영지원 관리 엑셀 이관 (조원 저장소 ledger/import 규칙, 시험 파일은 가상 데이터)"""

    def setUp(self):
        self.client.force_authenticate(make_user("mgmt", User.Role.MEMBER, [M]))

    def upload(self, url, name="ledger-sample.xlsx", **data):
        with open(TEST_FILES / name, "rb") as f:
            return self.client.post(url, {"year": 2026, "month": 10, "file": f, **data}, format="multipart")

    def preview(self, name="ledger-sample.xlsx"):
        return self.upload("/api/management/ledger/import/preview/", name)

    def run_import(self, preview, choices=None, mode="none", name="ledger-sample.xlsx"):
        ap_rows = [r["row"] for b in preview["blocks"] if b["kind"] == "ap" for r in b["rows"]]
        choices = choices if choices is not None else {"purchase_type": {str(r): "raw_material" for r in ap_rows}}
        return self.upload("/api/management/ledger/import/", name, file_sha256=preview["file_sha256"], mode=mode,
                           expected_existing=preview["existing_total"], choices=json.dumps(choices))

    def test_preview_reads_without_saving(self, *_):
        res = self.preview()
        self.assertEqual(res.status_code, 200)
        ar = res.data["blocks"][0]
        self.assertEqual([r["ar_status"] for r in ar["rows"]][:3], ["long_overdue", "long_overdue", "collected"])
        self.assertEqual(str(next(r for r in ar["rows"] if r["row"] == 8)["settled_on"]), "2026-10-15")  # 적요 날짜
        vendor = res.data["blocks"][3]
        self.assertEqual(vendor["auto_transfer_sum"], 165000)
        self.assertEqual(LedgerEntry.objects.count(), 0)  # 미리보기는 저장하지 않음

    def test_import_needs_purchase_type_then_saves(self, *_):
        p = self.preview().data
        res = self.run_import(p, choices={})
        self.assertEqual(res.status_code, 400)
        self.assertIn("매입유형을 고르세요", res.data["detail"])
        res = self.run_import(p)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["saved"], 16)
        e = LedgerEntry.objects.get(partner_name="라마테크(가상)")
        self.assertEqual((e.partner_code, e.ar_status, e.settled_on), ("0000000118", "collected", date(2026, 10, 31)))
        self.assertTrue(LedgerEntry.objects.get(partner_name="타파통신(가상)").auto_transfer)
        log = AuditLog.objects.get(screen="ledger-import")
        self.assertEqual((log.action, log.meta["saved_rows"], log.meta["mode"]), ("IMPORT", 16, "추가"))

    def test_existing_rows_need_mode_and_overwrite_hides(self, *_):
        LedgerEntry.objects.create(year=2026, month=10, kind="ap", purchase_type="goods", partner_name="기존", amount=1)
        p = self.preview().data
        self.assertEqual(p["existing_total"], 1)
        self.assertEqual(self.run_import(p).status_code, 400)  # 덮어쓰기·추가를 안 고름
        res = self.run_import(p, mode="overwrite")
        self.assertEqual((res.status_code, res.data["hidden"]), (200, 1))
        self.assertIsNotNone(LedgerEntry.objects.get(partner_name="기존").deleted_at)  # 지우지 않고 숨김

    def test_changed_file_or_existing_rejected(self, *_):
        p = self.preview().data
        self.assertEqual(self.run_import({**p, "file_sha256": "0" * 64}).status_code, 400)
        LedgerEntry.objects.create(year=2026, month=10, kind="ap", purchase_type="goods", partner_name="그사이", amount=1)
        self.assertEqual(self.run_import(p).status_code, 409)

    def test_issues_file(self, *_):
        p = self.preview("ledger-sample-issues.xlsx").data
        ar = p["blocks"][0]
        self.assertEqual((ar["skipped_code_only"], ar["skipped_zero"]), ([30], [29]))
        self.assertEqual(p["blocks"][1]["totals"][0]["state"], "mismatch")
        unclassified = [r["row"] for r in ar["rows"] if r["ar_status"] is None]
        self.assertEqual(unclassified, [25, 26, 28])
        res = self.run_import(p, name="ledger-sample-issues.xlsx")
        self.assertIn("상태(미분류)를 고르세요", res.data["detail"])
        choices = {
            "purchase_type": {"41": "goods", "42": "goods", "43": "goods"},
            "ar_status": {"25": "scheduled", "26": "collected", "28": "long_overdue"},
            "settled_on": {"26": "2026-10-20"},
        }
        res = self.run_import(p, choices=choices, name="ledger-sample-issues.xlsx")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(LedgerEntry.objects.get(partner_name="사아워터(가상)").settled_on, date(2026, 10, 20))

    def test_not_a_ledger_file(self, *_):
        from openpyxl import Workbook

        buf = BytesIO()
        Workbook().save(buf)
        buf.name = "빈파일.xlsx"
        buf.seek(0)
        res = self.client.post("/api/management/ledger/import/preview/", {"year": 2026, "month": 10, "file": buf}, format="multipart")
        self.assertEqual(res.status_code, 400)
        self.assertIn("양식이 아닙니다", res.data["detail"])


@patch("management.export.timezone.localdate", return_value=TODAY)
@patch("management.ledger_views.timezone.localdate", return_value=TODAY)
@patch("management.ledger_import_views.timezone.localdate", return_value=TODAY)
class LedgerExportTests(APITestCase):
    """경영지원 관리 엑셀 내려받기 — 내려받은 파일을 다시 올려도 같은 값으로 읽혀야 한다 (왕복)"""

    def setUp(self):
        self.client.force_authenticate(make_user("mgmt", User.Role.MEMBER, [M]))
        add = lambda **kw: LedgerEntry.objects.create(year=2026, month=10, **kw)  # noqa: E731
        add(kind="ar", ar_status="long_overdue", partner_code="0000000087", partner_name="가나", amount=100, note="오래됨")
        add(kind="ar", ar_status="collected", partner_code="0000000102", partner_name="다라", amount=200, note="", settled_on=date(2026, 10, 15))
        add(kind="ar", ar_status="scheduled", partner_name="마바", amount=300, note="10/20")
        add(kind="ap", purchase_type="goods", partner_name="사아", amount=400)
        add(kind="accrued_vendor", expense_type="other", auto_transfer=True, partner_name="통신", amount=50, note="인터넷")
        add(kind="accrued_vendor", expense_type="advertising", partner_name="광고", amount=60)
        add(kind="ap", purchase_type="goods", partner_name="숨김", amount=1, deleted_at="2026-10-30T00:00:00Z")

    def test_round_trip(self, *_):
        res = self.client.get("/api/management/ledger/export/?year=2026&period=month&month=10")
        self.assertEqual(res.status_code, 200)
        self.assertIn("2026-10.xlsx", res["Content-Disposition"])
        buf = BytesIO(res.content)
        buf.name = "경영지원_관리_2026-10.xlsx"
        preview = self.client.post("/api/management/ledger/import/preview/", {"year": 2026, "month": 10, "file": buf}, format="multipart")
        self.assertEqual(preview.status_code, 200)
        p = preview.data
        self.assertEqual(p["fatal"], [])
        rows = {r["partner_name"]: r for b in p["blocks"] for r in b["rows"]}
        self.assertNotIn("숨김", rows)  # 숨긴 행은 내려받지 않음
        self.assertEqual((rows["가나"]["ar_status"], rows["가나"]["ar_status_source"], rows["가나"]["partner_code"]), ("long_overdue", "red", "0000000087"))
        self.assertEqual((rows["다라"]["ar_status"], rows["다라"]["ar_status_source"]), ("collected", "memo"))
        self.assertEqual((rows["마바"]["ar_status"], rows["마바"]["note"]), ("scheduled", "10/20"))  # 적요가 날짜로 바뀌지 않음
        self.assertTrue(rows["통신"]["auto_transfer"])
        self.assertFalse(rows["광고"]["auto_transfer"])
        self.assertEqual(sum(len(b["rows"]) for b in p["blocks"]), 6)
        log = AuditLog.objects.get(screen="ledger-export")
        self.assertEqual((log.action, log.meta["rows"]), ("EXPORT", 6))

    def test_quarter_sheets_and_future(self, *_):
        res = self.client.get("/api/management/ledger/export/?year=2026&period=quarter&quarter=4")
        wb = load_workbook(BytesIO(res.content))
        self.assertEqual(wb.sheetnames, ["2026-10"])  # 데이터가 있는 달만
        ws = wb["2026-10"]
        self.assertEqual(ws["C1"].value, "외상매출금")
        self.assertEqual(ws["H3"].value, "← 장기 미수금 업체")
        res = self.client.get("/api/management/ledger/export/?year=2026&period=quarter&quarter=2")
        self.assertEqual(load_workbook(BytesIO(res.content)).sheetnames, ["2026-Q2"])  # 빈 양식 1장
        self.assertEqual(self.client.get("/api/management/ledger/export/?year=2027&period=year").status_code, 400)


class DetailMetricsTests(APITestCase):
    """경영지원 상세 지표 (조원 저장소 break-even·productivity·cash-forecast 규칙)"""

    def test_break_even(self):
        from .detail_metrics import break_even

        f = finance(2026, 9, product=1000, purchase=300, material=100, expense=200)
        ad = ExpenseCategory.objects.create(name="광고", cost_type="variable")
        etc = ExpenseCategory.objects.create(name="기타")  # 미분류 → 고정비
        OtherExpense.objects.create(monthly=f, category=ad, amount=100)
        OtherExpense.objects.create(monthly=f, category=etc, amount=50)
        rows = list(MonthlyFinance.objects.prefetch_related("other_expenses__category"))
        b = break_even(rows, 1000)
        self.assertEqual((b["variable_cost"], b["fixed_cost"], b["contribution"]), (500, 250, 500))
        self.assertEqual((b["bep_revenue"], b["rate"], b["gap"], b["unclassified_count"]), (500, 200.0, 500, 1))
        self.assertEqual(break_even(rows, 400)["reason"], "not-reachable")  # 변동비 ≥ 매출
        self.assertEqual(break_even([], 0)["reason"], "no-data")

    def test_productivity_rounds(self):
        from .detail_metrics import productivity

        self.assertEqual(productivity(3, True, 1000, -1000)["profit_per_head"], -333)
        self.assertEqual(productivity(None, True, 1, 1)["reason"], "no-headcount")
        self.assertEqual(productivity(12, False, 1, 1)["reason"], "no-data")

    def test_cash_forecast(self):
        from .detail_metrics import cash_forecast, with_vat

        today = date(2026, 11, 4)
        for m in (8, 9, 10):
            finance(2026, m, product=1000, expense=100)
        MonthlyFinance.objects.filter(month=10).update(cash_balance=5000)
        L = lambda **kw: LedgerEntry.objects.create(year=2026, month=10, partner_name="x", **kw)  # noqa: E731
        L(kind="ar", ar_status="scheduled", amount=300, due_on=date(2027, 1, 10))  # 1월에 들어옴
        L(kind="ar", ar_status="scheduled", amount=50)  # 예정일 없음 → 첫 달
        L(kind="ar", ar_status="long_overdue", amount=999)  # 넣지 않음
        L(kind="ap", purchase_type="goods", amount=200, due_on=date(2026, 12, 20))
        L(kind="ap", purchase_type="goods", amount=70)  # 예정일 없음 → 기준월 다음 달(11월) = 이미 지난 달
        c = cash_forecast(today)
        first, second = c["months"][0], c["months"][1]
        self.assertEqual((first["year"], first["month"]), (2026, 12))
        self.assertEqual((first["inflow_planned"], first["outflow_planned"]), (50, 200))
        self.assertEqual(second["inflow_planned"], 300)
        self.assertEqual(c["average"]["inflow"], with_vat(1000))  # 매출은 ×1.1
        self.assertEqual(c["average"]["outflow"], 100)  # 경비는 그대로
        self.assertEqual(first["inflow_estimated"], 1100)  # 기준월 10월 + 2 = 12월부터 추정
        self.assertEqual(first["balance"], 5000 + first["net"])
        self.assertEqual((c["notes"]["long_overdue"]["amount"], c["notes"]["past_outflow"]["amount"]), (999, 70))

    def test_detail_api(self):
        self.client.force_authenticate(make_user("mgmt", User.Role.MEMBER, [M]))
        res = self.client.get("/api/management/detail/?year=2026&period=quarter&quarter=3")
        self.assertEqual(res.status_code, 200)
        for key in ("break_even", "productivity", "receivables", "cash_forecast", "changes", "trend"):
            self.assertIn(key, res.data)
        self.client.force_authenticate(make_user("prod", User.Role.LEADER, [P], [P]))
        self.assertEqual(self.client.get("/api/management/detail/").status_code, 403)
