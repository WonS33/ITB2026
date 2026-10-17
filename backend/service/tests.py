from datetime import date

from rest_framework.test import APITestCase

from accounts.models import User
from common.periods import make_period

from .metrics import service_summary
from .models import TripReport, TripReportCompanion, TripReportPart, TripReportProduct

P = User.Team.PRODUCTION
S = User.Team.SERVICE


def make_report(start, requester, region, paid, author, companions=(), products=(), parts=()):
    r = TripReport.objects.create(start_date=start, requester=requester, region=region, paid_type=paid, author=author)
    for name in companions:
        TripReportCompanion.objects.create(report=r, name=name)
    for model, qty in products:
        TripReportProduct.objects.create(report=r, model_name=model, quantity=qty)
    for part in parts:
        TripReportPart.objects.create(report=r, part_name=part)
    return r


class ServiceSummaryTests(APITestCase):
    """specs/09-metrics.md 4절"""

    def setUp(self):
        # 작성자가 동행자에도 들어 있는 경우 (샘플과 같음) → 1회로 세야 함
        make_report(date(2026, 9, 29), "가람", "충청북도", "유상", "김가상", ["김가상"], [("AVA03", 1)],
                    ["Main Board", "Power Board"])
        make_report(date(2026, 10, 2), "나래", "경기도", "무상", "이가상", ["김가상"], [("AVA03", 2), ("AVA05", 1)],
                    ["Main Board"])
        make_report(date(2026, 10, 20), "다온", "경기도", "유상", "김가상", [], [("AVA05", 1)], [])
        make_report(date(2025, 10, 5), "라온", "제주특별자치도", "유상", "박가상")  # 다른 해

    def test_month(self):
        s = service_summary(make_period("month", 2026, month=10))
        self.assertEqual(s["trip_count"], 2)
        self.assertEqual(s["paid"], [{"name": "유상", "quantity": 1}, {"name": "무상", "quantity": 1}])
        self.assertEqual(s["by_region"], [{"name": "경기도", "quantity": 2}])
        # 수량이 같으면 이름순
        self.assertEqual(s["by_model"], [{"name": "AVA03", "quantity": 2}, {"name": "AVA05", "quantity": 2}])
        self.assertEqual(s["by_part"], [{"name": "Main Board", "quantity": 1}])

    def test_person_counted_once_per_report(self):
        s = service_summary(make_period("quarter", 2026, quarter=4))
        people = {p["name"]: p["quantity"] for p in s["by_person"]}
        self.assertEqual(people, {"김가상": 2, "이가상": 1})  # 10/2 동행 + 10/20 작성
        q3 = service_summary(make_period("quarter", 2026, quarter=3))
        self.assertEqual(q3["by_person"], [{"name": "김가상", "quantity": 1}])  # 작성자=동행자 → 1회

    def test_monthly_trend_and_multi_day_trip(self):
        s = service_summary(make_period("year", 2026))
        self.assertEqual(s["trip_count"], 3)
        counts = {m["month"]: m["count"] for m in s["monthly"]}
        self.assertEqual((counts[9], counts[10], counts[1]), (1, 2, 0))
        self.assertEqual(len(s["monthly"]), 12)


class ServiceApiTests(APITestCase):
    def setUp(self):
        self.report = make_report(date(2026, 10, 2), "나래", "경기도", "무상", "이가상", ["김가상"],
                                  [("AVA03", 2)], ["Main Board"])

    def login(self, view):
        self.client.force_authenticate(User.objects.create_user(f"u{User.objects.count()}", password="x",
                                                                 view_teams=list(view)))

    def test_dashboard_list_detail(self):
        self.login([S])
        res = self.client.get("/api/service/dashboard/", {"year": 2026, "period": "month", "month": 10})
        self.assertEqual(res.data["service"]["trip_count"], 1)
        res = self.client.get("/api/service/reports/", {"year": 2026, "period": "month", "month": 10})
        self.assertEqual([r["requester"] for r in res.data["results"]], ["나래"])
        res = self.client.get(f"/api/service/reports/{self.report.id}/")
        self.assertEqual((res.data["companions"], res.data["parts"]), (["김가상"], ["Main Board"]))

    def test_production_only_user_403(self):
        self.login([P])
        self.assertEqual(self.client.get("/api/service/dashboard/").status_code, 403)
        self.assertEqual(self.client.get(f"/api/service/reports/{self.report.id}/").status_code, 403)

    def test_anonymous_401(self):
        self.assertEqual(self.client.get("/api/service/reports/").status_code, 401)
