from datetime import date

from rest_framework.test import APITestCase

from accounts.models import User
from common.periods import make_period

from .metrics import production_summary
from .models import AnnualProductionTarget, ManufacturingRecord

P = User.Team.PRODUCTION
S = User.Team.SERVICE


def add_records(year, month, count, start=1):
    for i in range(start, start + count):
        ManufacturingRecord.objects.create(
            serial_full=f"N82{str(year)[2:]}{i:04d}",
            serial_short=f"{i:04d}",
            manufactured_date=date(year, month, 10),
        )


class ProductionSummaryTests(APITestCase):
    """specs/09-metrics.md 3절 계산식"""

    def setUp(self):
        AnnualProductionTarget.objects.create(year=2026, target_quantity=120)  # 월 목표 10대
        add_records(2026, 1, 12, start=1)  # 1월 12대
        add_records(2026, 2, 6, start=100)  # 2월 6대
        add_records(2025, 12, 5, start=200)  # 다른 해는 집계에서 빠져야 함

    def test_month_over_target_shortfall_is_zero(self):
        s = production_summary(make_period("month", 2026, month=1))
        self.assertEqual(s["actual"], 12)
        self.assertEqual(s["period_target"], 10.0)
        self.assertEqual(s["achievement_rate"], 120.0)
        self.assertEqual(s["shortfall"], 0)  # 목표 초과 → 부족치 0

    def test_quarter(self):
        s = production_summary(make_period("quarter", 2026, quarter=1))
        self.assertEqual(s["actual"], 18)
        self.assertEqual(s["period_target"], 30.0)  # 120 ÷ 12 × 3
        self.assertEqual(s["achievement_rate"], 60.0)
        self.assertEqual(s["shortfall"], 12.0)

    def test_year(self):
        s = production_summary(make_period("year", 2026))
        self.assertEqual(s["actual"], 18)
        self.assertEqual(s["shortfall"], 102.0)

    def test_no_target_returns_none(self):
        s = production_summary(make_period("year", 2025))
        self.assertEqual(s["actual"], 5)
        self.assertIsNone(s["achievement_rate"])
        self.assertIsNone(s["shortfall"])

    def test_zero_target_has_no_rate(self):
        AnnualProductionTarget.objects.filter(year=2026).update(target_quantity=0)
        s = production_summary(make_period("year", 2026))
        self.assertIsNone(s["achievement_rate"])
        self.assertEqual(s["shortfall"], 0)


class ProductionApiTests(APITestCase):
    def login(self, role, view=(), edit=()):
        user = User.objects.create_user(f"u_{role}_{len(view)}{len(edit)}", password="x", role=role,
                                        view_teams=list(view), edit_teams=list(edit))
        self.client.force_authenticate(user)
        return user

    def test_leader_can_set_target(self):
        self.login(User.Role.LEADER, [P], [P])
        res = self.client.put("/api/production/targets/2026/", {"target_quantity": 300}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.client.get("/api/production/targets/2026/").data["target_quantity"], 300)

    def test_member_can_view_but_not_set_target(self):
        self.login(User.Role.MEMBER, [P])
        self.assertEqual(self.client.get("/api/production/targets/2026/").status_code, 200)
        res = self.client.put("/api/production/targets/2026/", {"target_quantity": 300}, format="json")
        self.assertEqual(res.status_code, 403)

    def test_service_member_cannot_view(self):
        self.login(User.Role.MEMBER, [S])
        self.assertEqual(self.client.get("/api/production/dashboard/").status_code, 403)

    def test_anonymous_401(self):
        self.assertEqual(self.client.get("/api/production/dashboard/").status_code, 401)

    def test_invalid_target_400(self):
        self.login(User.Role.ADMIN)
        res = self.client.put("/api/production/targets/2026/", {"target_quantity": -1}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_dashboard(self):
        self.login(User.Role.LEADER, [P], [P])
        AnnualProductionTarget.objects.create(year=2026, target_quantity=120)
        add_records(2026, 10, 4)
        res = self.client.get("/api/production/dashboard/?year=2026&period=month&month=10")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["period"]["label"], "2026년 10월")
        self.assertEqual(res.data["production"]["actual"], 4)
        self.assertEqual(res.data["production"]["achievement_rate"], 40.0)
