import os
from datetime import date

from rest_framework.test import APITestCase

from accounts.models import User
from common.periods import make_period

from .metrics import service_summary
from .models import PartPrice, RequesterRegion, TripReport, TripReportCompanion, TripReportPart, TripReportProduct
from .part_prices import part_price_table

P = User.Team.PRODUCTION
S = User.Team.SERVICE


def make_report(start, requester, region, paid, author, companions=(), products=(), parts=(), district=""):
    r = TripReport.objects.create(start_date=start, requester=requester, region=region, district=district,
                                  paid_type=paid, author=author)
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
                    ["Main Board"], district="화성시")
        make_report(date(2026, 10, 20), "다온", "경기도", "유상", "김가상", [], [("AVA05", 1)], [])  # 시·군 미지정
        make_report(date(2026, 10, 21), "마루", "부산광역시", "유상", "김가상", district="")
        make_report(date(2026, 10, 22), "바다", "경기도", "무상", "이가상", district="화성시")
        make_report(date(2025, 10, 5), "라온", "제주특별자치도", "유상", "박가상")  # 다른 해

    def test_month(self):
        s = service_summary(make_period("month", 2026, month=10))
        self.assertEqual(s["trip_count"], 4)
        self.assertEqual(s["paid"], [{"name": "유상", "quantity": 2}, {"name": "무상", "quantity": 2}])
        self.assertEqual([(r["name"], r["quantity"]) for r in s["by_region"]], [("경기도", 3), ("부산광역시", 1)])
        # 수량이 같으면 이름순
        self.assertEqual(s["by_model"], [{"name": "AVA03", "quantity": 2}, {"name": "AVA05", "quantity": 2}])
        self.assertEqual(s["by_part"], [{"name": "Main Board", "quantity": 1}])

    def test_by_district(self):
        """시·군별: 도는 시·군까지, 특별·광역시는 시·도 하나로, 시·군이 비면 '미지정'"""
        s = service_summary(make_period("month", 2026, month=10))
        self.assertEqual(s["by_district"], [
            {"name": "경기 화성시", "quantity": 2, "region": "경기도", "district": "화성시"},
            {"name": "경기도 (시·군 미지정)", "quantity": 1, "region": "경기도", "district": ""},
            {"name": "부산광역시", "quantity": 1, "region": "부산광역시", "district": ""},
        ])

    def test_person_counted_once_per_report(self):
        s = service_summary(make_period("quarter", 2026, quarter=4))
        people = {p["name"]: p["quantity"] for p in s["by_person"]}
        self.assertEqual(people, {"김가상": 3, "이가상": 2})  # 김: 10/2 동행 + 10/20·10/21 작성
        q3 = service_summary(make_period("quarter", 2026, quarter=3))
        self.assertEqual(q3["by_person"], [{"name": "김가상", "quantity": 1}])  # 작성자=동행자 → 1회

    def test_monthly_trend_and_multi_day_trip(self):
        s = service_summary(make_period("year", 2026))
        self.assertEqual(s["trip_count"], 5)
        counts = {m["month"]: m["count"] for m in s["monthly"]}
        self.assertEqual((counts[9], counts[10], counts[1]), (1, 4, 0))
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


class PartPriceTests(APITestCase):
    """교체 부품 단가: 현재·직전 단가, 증감, 미등록 부품, 입력·삭제 권한"""

    def setUp(self):
        make_report(date(2026, 9, 1), "가람", "충청북도", "유상", "김가상", parts=["Main Board", "Motor"], district="청주시")
        make_report(date(2026, 10, 1), "나래", "경기도", "유상", "김가상", parts=["Main Board"], district="화성시")
        for price, day in ((100000, date(2026, 1, 1)), (120000, date(2026, 7, 1)), (150000, date(2027, 1, 1))):
            PartPrice.objects.create(part_name="Main Board", unit_price=price, effective_date=day)

    def test_current_previous_change(self):
        table = part_price_table(today=date(2026, 10, 21))
        board = table["parts"][0]
        self.assertEqual((board["part_name"], board["usage_count"]), ("Main Board", 2))
        # 2027-01-01 단가는 아직 적용 전(예정) → 현재 단가가 아님
        self.assertEqual((board["current_price"], board["previous_price"]), (120000, 100000))
        self.assertEqual((board["change"], board["change_rate"]), (20000, 20.0))
        self.assertEqual([h["upcoming"] for h in board["history"]], [False, False, True])
        self.assertEqual(table["unregistered"], [{"part_name": "Motor", "usage_count": 1}])
        self.assertEqual(table["part_names"], ["Main Board", "Motor"])

    def test_single_price_has_no_change(self):
        PartPrice.objects.create(part_name="Motor", unit_price=50000, effective_date=date(2026, 3, 1))
        motor = next(p for p in part_price_table(today=date(2026, 10, 21))["parts"] if p["part_name"] == "Motor")
        self.assertEqual((motor["current_price"], motor["previous_price"], motor["change"]), (50000, None, None))

    def login(self, edit):
        self.client.force_authenticate(User.objects.create_user(
            f"u{User.objects.count()}", password="x", role=User.Role.LEADER if edit else User.Role.MEMBER,
            view_teams=[S], edit_teams=[S] if edit else []))

    def test_add_and_delete_price(self):
        self.login(edit=True)
        res = self.client.post("/api/service/part-prices/",
                               {"part_name": "Motor", "unit_price": 50000, "effective_date": "2026-10-01"}, format="json")
        self.assertEqual(res.status_code, 201)
        again = self.client.post("/api/service/part-prices/",
                                 {"part_name": "Motor", "unit_price": 60000, "effective_date": "2026-10-01"}, format="json")
        self.assertEqual(again.status_code, 400)
        self.assertIn("effective_date", again.data)  # 같은 부품·같은 적용 시작일은 한 줄만
        bad = self.client.post("/api/service/part-prices/",
                               {"part_name": "Motor", "unit_price": -1, "effective_date": "2026-11-01"}, format="json")
        self.assertIn("unit_price", bad.data)
        self.assertEqual(self.client.delete(f"/api/service/part-prices/{res.data['id']}/").status_code, 204)
        self.assertFalse(PartPrice.objects.filter(part_name="Motor").exists())

    def test_member_can_view_but_not_edit(self):
        self.login(edit=False)
        self.assertEqual(self.client.get("/api/service/part-prices/").status_code, 200)
        res = self.client.post("/api/service/part-prices/",
                               {"part_name": "Motor", "unit_price": 1, "effective_date": "2026-10-01"}, format="json")
        self.assertEqual(res.status_code, 403)
        price = PartPrice.objects.first()
        self.assertEqual(self.client.delete(f"/api/service/part-prices/{price.id}/").status_code, 403)


class RequesterRegionApiTests(APITestCase):
    """요청처 지역 관리: 대응표를 바꾸면 같은 요청처의 저장된 보고서 지역도 함께 바뀐다"""

    def setUp(self):
        self.mapping = RequesterRegion.objects.create(requester="가람", region="경기도", district="")
        make_report(date(2026, 9, 1), "가람", "경기도", "유상", "김가상")
        make_report(date(2026, 10, 1), "가람", "경기도", "무상", "김가상")
        make_report(date(2026, 10, 2), "나래", "경기도", "무상", "김가상", district="화성시")
        self.client.force_authenticate(User.objects.create_user(
            "svc", password="x", role=User.Role.LEADER, view_teams=[S], edit_teams=[S]))

    def test_list(self):
        res = self.client.get("/api/service/requester-regions/")
        self.assertEqual(res.data["results"][0]["report_count"], 2)
        self.assertIn("강릉시", res.data["districts"]["강원특별자치도"])

    def test_patch_updates_reports(self):
        res = self.client.patch(f"/api/service/requester-regions/{self.mapping.id}/",
                                {"region": "충청북도", "district": "청주시"}, format="json")
        self.assertEqual((res.status_code, res.data["report_count"]), (200, 2))
        self.assertEqual(set(TripReport.objects.filter(requester="가람").values_list("region", "district")),
                         {("충청북도", "청주시")})
        self.assertEqual(TripReport.objects.get(requester="나래").district, "화성시")  # 다른 요청처는 그대로

    def test_patch_validation_and_permission(self):
        url = f"/api/service/requester-regions/{self.mapping.id}/"
        self.assertIn("district", self.client.patch(url, {"region": "충청북도", "district": ""}, format="json").data)
        self.assertEqual(self.client.patch(url, {"region": "서울특별시", "district": ""}, format="json").status_code, 200)
        self.client.force_authenticate(User.objects.create_user(
            "member", password="x", role=User.Role.MEMBER, view_teams=[S]))
        self.assertEqual(self.client.patch(url, {"region": "경기도", "district": "화성시"}, format="json").status_code, 403)


class SeedPartPricesTests(APITestCase):
    def test_seed_is_virtual_and_does_not_overwrite(self):
        from django.core.management import call_command

        from .management.commands.seed_part_prices import VIRTUAL_PRICES
        from .management.commands.seed_service import PARTS

        self.assertEqual(set(VIRTUAL_PRICES), set(PARTS))  # 가상 출장보고서의 부품과 같은 이름
        PartPrice.objects.create(part_name="Motor", unit_price=1, effective_date=date(2026, 1, 1))  # 사람이 입력한 값
        call_command("seed_part_prices", stdout=open(os.devnull, "w"))
        call_command("seed_part_prices", stdout=open(os.devnull, "w"))  # 두 번 실행해도 늘어나지 않음
        self.assertEqual(list(PartPrice.objects.filter(part_name="Motor").values_list("unit_price", flat=True)), [1])
        expected = sum(len(v) for k, v in VIRTUAL_PRICES.items() if k != "Motor") + 1
        self.assertEqual(PartPrice.objects.count(), expected)


class TripReportManualInputTests(APITestCase):
    """출장보고서 직접 입력: PDF 업로드와 같은 규칙으로 검사·저장"""

    URL = "/api/service/reports/"

    def setUp(self):
        self.client.force_authenticate(User.objects.create_user(
            "svc", password="x", role=User.Role.LEADER, view_teams=[S], edit_teams=[S]))

    def body(self, **overrides):
        data = {"start_date": "2026-10-20", "end_date": "2026-10-21", "requester": "새빛정수장", "region": "강원특별자치도",
                "district": "강릉시", "paid_type": "유상", "author": "김가상 대리", "work_type": "수리", "purpose": "가상 A/S",
                "companions": ["이가상 사원", " "], "parts": ["Main Board", "Motor"],
                "products": [{"model_name": "AVA03", "spec": "380V", "serial_no_raw": "A800", "quantity": "2"},
                             {"model_name": "", "spec": "", "serial_no_raw": "", "quantity": ""}],  # 빈 줄은 무시
                "fault_description": "1. 가상 고장", "work_description": "1. 가상 작업", "work_result": "정상작동"}
        data.update(overrides)
        return data

    def test_create_with_children_and_remember_region(self):
        res = self.client.post(self.URL, self.body(), format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual((res.data["input_method"], res.data["input_method_display"]), ("manual", "직접 입력"))
        self.assertEqual(res.data["companions"], ["이가상 사원"])
        self.assertEqual(res.data["products"], [{"model_name": "AVA03", "spec": "380V", "serial_no_raw": "A800", "quantity": 2}])
        self.assertEqual(res.data["parts"], ["Main Board", "Motor"])
        mapping = RequesterRegion.objects.get(requester="새빛정수장")
        self.assertEqual((mapping.region, mapping.district), ("강원특별자치도", "강릉시"))
        # 대시보드 집계에도 그대로 들어감
        s = service_summary(make_period("month", 2026, month=10))
        self.assertEqual(s["by_district"][0]["name"], "강원 강릉시")

    def test_validation_same_as_upload(self):
        res = self.client.post(self.URL, self.body(start_date="", district="청주시", paid_type="반반", author=" ",
                                                   products=[{"model_name": "AVA03", "quantity": "0"}],
                                                   parts=["Magnetic Contactor (TR Cont…"]), format="json")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(set(res.data), {"start_date", "district", "paid_type", "author", "products", "parts"})
        self.assertEqual(self.client.post(self.URL, self.body(end_date="2026-10-01"), format="json").data["end_date"],
                         "종료일이 시작일보다 빠릅니다.")
        bad_type = self.client.post(self.URL, self.body(companions="이가상"), format="json")
        self.assertEqual(bad_type.status_code, 400)
        self.assertFalse(TripReport.objects.exists())

    def test_duplicate_needs_confirmation(self):
        self.assertEqual(self.client.post(self.URL, self.body(), format="json").status_code, 201)
        again = self.client.post(self.URL, self.body(author="박다른 과장"), format="json")
        self.assertEqual(again.status_code, 409)
        self.assertEqual(again.data["existing"][0]["author"], "김가상 대리")
        confirmed = self.client.post(self.URL, self.body(author="박다른 과장", allow_duplicate=True), format="json")
        self.assertEqual(confirmed.status_code, 201)
        self.assertEqual(TripReport.objects.count(), 2)

    def test_permissions(self):
        self.client.force_authenticate(User.objects.create_user(
            "member", password="x", role=User.Role.MEMBER, view_teams=[S]))
        self.assertEqual(self.client.post(self.URL, self.body(), format="json").status_code, 403)
        self.client.force_authenticate(User.objects.create_user(
            "prod", password="x", role=User.Role.LEADER, view_teams=[P], edit_teams=[P]))
        self.assertEqual(self.client.post(self.URL, self.body(), format="json").status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post(self.URL, self.body(), format="json").status_code, 401)
