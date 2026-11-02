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
        self.assertEqual(s["by_model"], [{"name": "AVA03", "quantity": 2, "paid": 0, "unpaid": 2},
                                         {"name": "AVA05", "quantity": 2, "paid": 1, "unpaid": 1}])
        self.assertEqual([(p["name"], p["quantity"], p["current_price"]) for p in s["by_part"]], [("Main Board", 1, None)])

    def test_by_district(self):
        """시·군별: 도는 시·군까지, 특별·광역시는 시·도 하나로, 시·군이 비면 '미지정'"""
        s = service_summary(make_period("month", 2026, month=10))
        self.assertEqual(s["by_district"], [
            {"name": "경기 화성시", "quantity": 2, "region": "경기도", "district": "화성시"},
            {"name": "경기도 (시·군 미지정)", "quantity": 1, "region": "경기도", "district": ""},
            {"name": "부산광역시", "quantity": 1, "region": "부산광역시", "district": ""},
        ])

    def test_part_ranking_has_current_price(self):
        PartPrice.objects.create(part_name="Main Board", unit_price=100000, effective_date=date(2026, 1, 1))
        PartPrice.objects.create(part_name="Main Board", unit_price=110000, effective_date=date(2026, 6, 1))
        part = service_summary(make_period("month", 2026, month=10))["by_part"][0]
        self.assertEqual((part["current_price"], part["change"], part["change_rate"]), (110000, 10000, 10.0))

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
        october = s["monthly"][9]
        self.assertEqual((october["paid"], october["unpaid"]), (2, 2))  # 월별 유상·무상 나눠서
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
        from .models import PartCatalogItem

        item = PartCatalogItem.objects.create(part_no="VX-05-A-01", name="Motor", list_price=500000)
        self.login(edit=True)
        body = {"catalog_item": item.id, "quote_company": "가상정수센터", "unit_price": 50000, "effective_date": "2026-10-01"}
        res = self.client.post("/api/service/part-prices/", body, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["part_name"], "Motor")  # 부품명은 단가표 품명으로 채움
        again = self.client.post("/api/service/part-prices/", {**body, "unit_price": 60000}, format="json")
        self.assertEqual(again.status_code, 400)
        self.assertIn("effective_date", again.data)  # 같은 부품·같은 업체·같은 날짜는 한 줄만
        other = self.client.post("/api/service/part-prices/", {**body, "quote_company": "가상발전소"}, format="json")
        self.assertEqual(other.status_code, 201)  # 업체가 다르면 같은 날짜도 따로
        bad = self.client.post("/api/service/part-prices/", {**body, "unit_price": -1, "quote_company": ""}, format="json")
        self.assertIn("unit_price", bad.data)
        self.assertIn("quote_company", bad.data)
        self.assertEqual(self.client.delete(f"/api/service/part-prices/{res.data['id']}/").status_code, 204)
        self.assertEqual(PartPrice.objects.filter(catalog_item=item).count(), 1)

    def test_member_can_view_but_not_edit(self):
        self.login(edit=False)
        self.assertEqual(self.client.get("/api/service/part-prices/").status_code, 200)
        res = self.client.post("/api/service/part-prices/",
                               {"part_name": "Motor", "unit_price": 1, "effective_date": "2026-10-01"}, format="json")
        self.assertEqual(res.status_code, 403)
        price = PartPrice.objects.first()
        self.assertEqual(self.client.delete(f"/api/service/part-prices/{price.id}/").status_code, 403)


class PartCatalogTests(APITestCase):
    """부품 단가표: 파일 읽기, 뉴토크 기준값, 출장지(업체)별 평균·최저·최고·최고−최저, 검색, 설정 권한 (가상 값)"""

    TODAY = date(2026, 11, 2)

    def setUp(self):
        from .models import PartCatalogItem

        self.motor = PartCatalogItem.objects.create(part_no="VX-05-A-01", category="05 MOTOR", name="Motor",
                                                    applies_to="NTI-01 ~ 03", list_price=500000, sort_order=1)
        self.board = PartCatalogItem.objects.create(part_no="VX-07-A-01", category="07 BOARD", name="Main Board",
                                                    list_price=None, sort_order=2)
        for company, day, price in (("가람", date(2026, 3, 1), 480000), ("다온", date(2026, 5, 1), 560000),
                                    ("가람", date(2026, 9, 1), 520000),   # 같은 업체 재견적 → 최근 것만
                                    ("나래", date(2026, 12, 1), 900000)):  # 아직 적용 전 → 빼야 함
            PartPrice.objects.create(part_name="Motor", catalog_item=self.motor, quote_company=company,
                                     effective_date=day, unit_price=price)

    def test_parse_catalog_csv(self):
        from .catalog import parse_catalog

        raw = ("[가상] 제목 줄,,,\n종류,,, 기준단가 \n05 MOTOR,,,\n"
               'VX-05-A-01,Motor,NTI-01 ~ 03," 500,000 "\nVX-05-A-02,Motor,NTI-04 ~ 05, - \n'
               '07 BOARD,,,\nVX-07-D-01,가상 부품A,," 1,000 "\nVX-07-D-01,가상 부품B,," 2,000 "\n')
        items, warnings = parse_catalog(("﻿" + raw).encode("utf-8"))
        self.assertEqual([(i["part_no"], i["category"], i["list_price"]) for i in items], [
            ("VX-05-A-01", "05 MOTOR", 500000), ("VX-05-A-02", "05 MOTOR", None),
            ("VX-07-D-01", "07 BOARD", 1000), ("VX-07-D-01", "07 BOARD", 2000)])
        self.assertEqual(len(warnings), 1)  # 같은 파트넘버가 두 품목
        cp949_items, _ = parse_catalog(raw.encode("cp949"))  # 한글 윈도우 인코딩도 읽음
        self.assertEqual(cp949_items[2]["name"], "가상 부품A")

    def test_standard_price_and_stats(self):
        from .catalog import catalog_table
        from .models import PriceStandard

        standard = PriceStandard.get()
        standard.default_discount_rate, standard.default_extra_price = 10, 5000
        standard.save()
        rows = {r["part_no"]: r for r in catalog_table(today=self.TODAY)["items"]}
        motor = rows["VX-05-A-01"]
        self.assertEqual(motor["standard_price"], 455000)  # 500,000 × 0.9 + 5,000
        self.assertFalse(motor["custom"])
        # 가람 520,000(최근) · 다온 560,000 → 평균 540,000, 최저 520,000, 최고 560,000, 차이 40,000
        self.assertEqual(motor["stats"], {"count": 2, "average": 540000, "min": 520000, "max": 560000, "range": 40000})
        self.assertIsNone(rows["VX-07-A-01"]["standard_price"])  # 기준단가 없음
        self.assertEqual(rows["VX-07-A-01"]["stats"]["count"], 0)

        self.motor.discount_rate, self.motor.extra_price = 0, 0  # 부품별 설정이 기본값보다 우선
        self.motor.save()
        self.assertEqual(catalog_table(today=self.TODAY)["items"][0]["standard_price"], 500000)

    def test_search_by_part_no(self):
        from .catalog import catalog_table

        for query in ("vx05a", "05-A-01", "0501", " VX-05-A-01 "):
            self.assertEqual([r["part_no"] for r in catalog_table(query, today=self.TODAY)["items"]], ["VX-05-A-01"], query)
        self.assertEqual([r["part_no"] for r in catalog_table("board", today=self.TODAY)["items"]], ["VX-07-A-01"])
        self.assertEqual(catalog_table(category="07 BOARD", today=self.TODAY)["items"][0]["name"], "Main Board")
        self.assertEqual(catalog_table(today=self.TODAY)["categories"], ["05 MOTOR", "07 BOARD"])  # 중복 없이

    def test_detail_diff_and_latest(self):
        from .catalog import catalog_detail

        d = catalog_detail(self.motor, today=self.TODAY)
        latest = {(p["company"], p["unit_price"]) for p in d["prices"] if p["latest"]}
        self.assertEqual(latest, {("가람", 520000), ("다온", 560000)})
        dao = next(p for p in d["prices"] if p["company"] == "다온")
        self.assertEqual((dao["diff"], dao["diff_rate"]), (60000, 12.0))  # 기준값 500,000 대비
        self.assertTrue(next(p for p in d["prices"] if p["company"] == "나래")["upcoming"])

    def test_company_comparison(self):
        from .catalog import company_comparison

        rows = {r["company"]: r for r in company_comparison(today=self.TODAY)["companies"]}
        self.assertEqual(set(rows), {"가람", "다온"})  # 적용 전 단가만 있는 나래는 빠짐, 기준값 없는 부품도 빠짐
        self.assertEqual((rows["다온"]["average_rate"], rows["다온"]["above"]), (12.0, 1))  # 560,000 vs 500,000
        self.assertEqual(rows["가람"]["parts"][0]["unit_price"], 520000)  # 최근 단가만
        self.assertEqual([r["company"] for r in company_comparison(today=self.TODAY)["companies"]], ["다온", "가람"])
        self.assertEqual(company_comparison("07 BOARD", today=self.TODAY)["companies"], [])

    def test_compare_with_price_list_of_quote_date(self):
        """단가표 개정 이력: 견적은 그 당시 단가표 기준값과 비교 (2026-11-02)"""
        from .catalog import catalog_detail, company_comparison
        from .models import PartListPrice

        PartListPrice.objects.create(item=self.motor, list_price=400000, effective_date=date(2026, 1, 1))
        PartListPrice.objects.create(item=self.motor, list_price=500000, effective_date=date(2026, 8, 1))
        d = catalog_detail(self.motor, today=self.TODAY)
        dao = next(p for p in d["prices"] if p["company"] == "다온")  # 5/1 견적 → 1/1 단가표 400,000
        self.assertEqual((dao["base_price"], dao["diff_rate"]), (400000, 40.0))
        garam = next(p for p in d["prices"] if p["company"] == "가람" and p["latest"])  # 9/1 견적 → 8/1 단가표
        self.assertEqual((garam["base_price"], garam["diff_rate"]), (500000, 4.0))
        self.assertEqual([r["list_price"] for r in d["revisions"]], [500000, 400000])  # 최근 기준일부터
        rows = {r["company"]: r for r in company_comparison(today=self.TODAY)["companies"]}
        self.assertEqual(rows["다온"]["average_rate"], 40.0)

    def test_low_alert(self):
        """기준값보다 크게 낮은 견적 표시 (할인 과다 점검)"""
        from .catalog import catalog_detail, company_comparison
        from .models import PriceStandard

        PartPrice.objects.create(part_name="Motor", catalog_item=self.motor, quote_company="라온",
                                 effective_date=date(2026, 10, 1), unit_price=470000)  # 기준값 대비 −6%
        self.assertFalse(next(p for p in catalog_detail(self.motor, today=self.TODAY)["prices"] if p["company"] == "라온")["low"])
        standard = PriceStandard.get()
        standard.low_alert_rate = 5
        standard.save()
        raon = next(p for p in catalog_detail(self.motor, today=self.TODAY)["prices"] if p["company"] == "라온")
        self.assertTrue(raon["low"])
        result = company_comparison(today=self.TODAY)
        self.assertEqual((result["low_count"], result["low_alert_rate"]), (1, 5.0))

    def login(self, edit):
        self.client.force_authenticate(User.objects.create_user(
            f"u{User.objects.count()}", password="x", role=User.Role.LEADER if edit else User.Role.MEMBER,
            view_teams=[S], edit_teams=[S] if edit else []))

    def test_api_and_permissions(self):
        self.login(edit=False)
        self.assertEqual(self.client.get("/api/service/part-catalog/?q=VX-05").status_code, 200)
        self.assertEqual(self.client.get(f"/api/service/part-catalog/{self.motor.id}/").status_code, 200)
        self.assertEqual(self.client.get("/api/service/part-catalog/companies/").status_code, 200)
        body = {"discount_rate": 5, "extra_price": 1000}
        self.assertEqual(self.client.patch(f"/api/service/part-catalog/{self.motor.id}/", body, format="json").status_code, 403)
        self.assertEqual(self.client.put("/api/service/price-standard/", body, format="json").status_code, 403)

        self.login(edit=True)
        res = self.client.patch(f"/api/service/part-catalog/{self.motor.id}/", body, format="json")
        self.assertEqual(res.data["standard_price"], 476000)  # 500,000 × 0.95 + 1,000
        reset = self.client.patch(f"/api/service/part-catalog/{self.motor.id}/",
                                  {"discount_rate": None, "extra_price": None}, format="json")
        self.assertFalse(reset.data["custom"])
        self.assertEqual(self.client.put("/api/service/price-standard/", {"discount_rate": 150, "extra_price": 0},
                                         format="json").status_code, 400)
        res = self.client.put("/api/service/price-standard/", {"discount_rate": 0, "extra_price": 0, "low_alert_rate": 15},
                              format="json")
        self.assertEqual(res.data["low_alert_rate"], 15.0)
        for url in ("/api/service/part-catalog/export/?q=VX", "/api/service/part-catalog/companies/export/"):
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200, url)
            self.assertIn("spreadsheetml", res["Content-Type"])
        choices = self.client.get("/api/service/part-catalog/choices/").data
        self.assertEqual(choices["items"][0]["label"], "VX-05-A-01 Motor (NTI-01 ~ 03)")
        self.assertEqual(choices["companies"], ["가람", "나래", "다온"])

    def test_import_command(self):
        import tempfile

        from django.core.management import call_command

        from .models import PartCatalogItem

        content = '05 MOTOR,,,\nVX-05-A-01,Motor,NTI-01 ~ 03," 600,000 "\nVX-05-A-09,가상 신규,, - \n'
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(content)
        self.motor.discount_rate = 3
        self.motor.save()
        call_command("import_part_catalog", f.name, stdout=open(os.devnull, "w"))
        os.unlink(f.name)
        self.motor.refresh_from_db()
        self.assertEqual((self.motor.list_price, self.motor.discount_rate), (600000, 3))  # 갱신, 부품별 설정은 유지
        self.assertEqual(self.motor.list_price_date, date(2026, 11, 1))  # 기준일을 안 주면 임시 기준일
        self.assertTrue(PartCatalogItem.objects.filter(part_no="VX-05-A-09").exists())

        # 예전 기준일 단가표를 넣어도 지금 기준단가는 가장 최근 기준일 값 그대로, 이력은 둘 다 남음
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(content.replace("600,000", "550,000"))
        call_command("import_part_catalog", f.name, date="2026-06-01", stdout=open(os.devnull, "w"))
        os.unlink(f.name)
        self.motor.refresh_from_db()
        self.assertEqual((self.motor.list_price, self.motor.list_price_date), (600000, date(2026, 11, 1)))
        self.assertEqual(list(self.motor.list_prices.values_list("list_price", flat=True)), [550000, 600000])


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

        from .management.commands.seed_part_prices import VIRTUAL_CATALOG
        from .models import PartCatalogItem

        self.assertTrue(all(row[0].startswith("VX-") for row in VIRTUAL_CATALOG))  # 실제 파트넘버와 구분
        call_command("seed_part_prices", stdout=open(os.devnull, "w"))
        call_command("seed_part_prices", stdout=open(os.devnull, "w"))  # 두 번 실행해도 늘어나지 않음
        self.assertEqual(PartCatalogItem.objects.count(), len(VIRTUAL_CATALOG))

    def test_seed_skips_when_catalog_exists(self):
        from django.core.management import call_command

        from .models import PartCatalogItem

        PartCatalogItem.objects.create(part_no="XX-01-A-01", name="사람이 넣은 단가표")
        call_command("seed_part_prices", stdout=open(os.devnull, "w"))
        self.assertEqual(PartCatalogItem.objects.count(), 1)
        self.assertEqual(PartPrice.objects.count(), 0)


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


class SeedCompanyPricesTests(APITestCase):
    """가상 출장지 단가 예시: 단가표 부품에 만들고, 한 번만 만들고, --clear는 예시만 지움"""

    def test_create_and_clear_examples_only(self):
        from django.core.management import call_command

        from .management.commands.seed_company_prices import MARKER
        from .models import PartCatalogItem

        motor = PartCatalogItem.objects.create(part_no="VX-05-A-01", name="Motor", list_price=500000)
        PartCatalogItem.objects.create(part_no="VX-05-A-02", name="Motor", list_price=None)  # 기준단가 없음 → 건너뜀
        real = PartPrice.objects.create(part_name="Motor", catalog_item=motor, quote_company="실제 입력",
                                        effective_date=date(2026, 1, 1), unit_price=1)
        out = open(os.devnull, "w")
        call_command("seed_company_prices", share=1, stdout=out)
        examples = PartPrice.objects.filter(quote_note=MARKER)
        self.assertTrue(examples.exists())
        self.assertEqual(set(examples.values_list("catalog_item", flat=True)), {motor.id})
        self.assertTrue(all(450000 <= p <= 625000 for p in examples.values_list("unit_price", flat=True)))
        count = examples.count()
        call_command("seed_company_prices", share=1, stdout=out)  # 이미 있으면 더 만들지 않음
        self.assertEqual(examples.count(), count)
        call_command("seed_company_prices", clear=True, stdout=out)
        self.assertFalse(examples.exists())
        self.assertTrue(PartPrice.objects.filter(id=real.id).exists())  # 사람이 넣은 단가는 그대로
