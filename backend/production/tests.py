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


class SerialLookupTests(APITestCase):
    """specs/05-production.md 2절 일련번호 조회"""

    def setUp(self):
        user = User.objects.create_user("viewer", password="x", role=User.Role.MEMBER, view_teams=[P])
        self.client.force_authenticate(user)
        ManufacturingRecord.objects.create(
            serial_full="N82260001", serial_short="0001", model_name="NTI-04", bush_machining="301008",
            rpm="29", power="380/3/60", manufactured_date=date(2026, 1, 9), inspection_no="NTK26001",
            po_no="26006", customer="가람상수도사업소", due_date=date(2026, 1, 15), note="방폭",
        )
        ManufacturingRecord.objects.create(serial_full="M82250001", serial_short="0001",
                                           manufactured_date=date(2025, 3, 1))

    def search(self, q):
        return self.client.get("/api/production/serials/", {"q": q}).data["results"]

    def test_search_by_4_digits_returns_all_matches(self):
        results = self.search("0001")
        self.assertEqual([r["serial_full"] for r in results], ["N82260001", "M82250001"])  # 최근 제조 순
        self.assertEqual(len(self.search("1")), 2)  # 1 → 0001

    def test_search_by_full_number(self):
        self.assertEqual([r["serial_full"] for r in self.search("n82260001")], ["N82260001"])
        self.assertEqual(self.search("N82269999"), [])
        self.assertEqual(self.search(""), [])

    def test_detail_has_11_items(self):
        res = self.client.get("/api/production/serials/N82260001/")
        self.assertEqual(res.status_code, 200)
        items = res.data["items"]
        self.assertEqual([i["no"] for i in items], list(range(1, 12)))
        self.assertEqual(items[0]["value"]["부시 가공"], "Ø30x10x08")
        self.assertEqual(items[4]["value"]["PO번호"], "#26006")
        self.assertEqual(items[9]["value"], "2026-01-15")

    def test_detail_not_found_404(self):
        self.assertEqual(self.client.get("/api/production/serials/N00000000/").status_code, 404)

    def test_service_only_user_cannot_search(self):
        other = User.objects.create_user("svc", password="x", role=User.Role.MEMBER, view_teams=[S])
        self.client.force_authenticate(other)
        self.assertEqual(self.client.get("/api/production/serials/", {"q": "0001"}).status_code, 403)


class DueCalendarTests(APITestCase):
    """specs/05-production.md 3절 납기 캘린더"""

    def setUp(self):
        user = User.objects.create_user("viewer", password="x", role=User.Role.MEMBER, view_teams=[P])
        self.client.force_authenticate(user)
        for i, (due, po, customer) in enumerate([
            (date(2026, 10, 5), "26006", "가람"), (date(2026, 10, 5), "26006", "가람"),
            (date(2026, 10, 5), "26007", "나래"), (date(2026, 10, 20), "", "다온"),
            (date(2026, 11, 1), "26008", "라온"),  # 다른 달 → 빠짐
        ], start=1):
            ManufacturingRecord.objects.create(serial_full=f"N8226{i:04d}", serial_short=f"{i:04d}",
                                               due_date=due, po_no=po, customer=customer)

    def test_groups_by_date_and_order_number(self):
        res = self.client.get("/api/production/due-calendar/", {"year": 2026, "month": 10})
        self.assertEqual(res.status_code, 200)
        days = {d["date"]: d["orders"] for d in res.data["days"]}
        self.assertEqual(list(days), ["2026-10-05", "2026-10-20"])
        first = days["2026-10-05"]
        self.assertEqual([(o["po_no"], o["quantity"]) for o in first], [("26006", 2), ("26007", 1)])
        self.assertEqual(first[0]["customers"], ["가람"])
        self.assertEqual(days["2026-10-20"][0]["po_no"], "")  # 수주번호 없음도 표시

    def test_invalid_month_400(self):
        self.assertEqual(self.client.get("/api/production/due-calendar/", {"year": 2026, "month": 13}).status_code, 400)

    def test_service_only_user_403(self):
        self.client.force_authenticate(User.objects.create_user("svc", password="x", view_teams=[S]))
        self.assertEqual(self.client.get("/api/production/due-calendar/").status_code, 403)


class DueStatusTests(APITestCase):
    """납기 처리 상태(출고일 기준)와 메인 대시보드 납기 임박 목록"""

    TODAY = date(2026, 10, 27)

    def setUp(self):
        self.client.force_authenticate(User.objects.create_user("viewer", password="x", role=User.Role.MEMBER,
                                                                view_teams=[P]))
        rows = [  # (납기일, 수주번호, 출고일)
            (date(2026, 10, 10), "26001", date(2026, 10, 8)),                       # 완료
            (date(2026, 10, 20), "26002", None),                                    # 납기 지남·미출고
            (date(2026, 10, 27), "26003", date(2026, 10, 25)), (date(2026, 10, 27), "26003", None),  # 오늘 납기, 일부 출고
            (date(2026, 11, 5), "26004", None), (date(2026, 11, 5), "26004", None),  # D-9, 출고 전
            (date(2026, 11, 20), "26005", None),                                    # 14일 넘음 → 임박 목록 제외
            (date(2026, 9, 1), "26000", None),                                      # 30일 넘게 지남 → 제외
        ]
        for i, (due, po, shipped) in enumerate(rows, start=1):
            ManufacturingRecord.objects.create(serial_full=f"N8226{i:04d}", serial_short=f"{i:04d}", due_date=due,
                                               po_no=po, customer="가상", shipped_date=shipped)

    def test_calendar_status(self):
        from .due_calendar import due_calendar

        days = {d["date"]: d["orders"][0] for d in due_calendar(2026, 10, today=self.TODAY)["days"]}
        self.assertEqual((days["2026-10-10"]["status"], days["2026-10-10"]["overdue"]), ("done", False))
        self.assertEqual((days["2026-10-20"]["status"], days["2026-10-20"]["overdue"]), ("pending", True))
        self.assertEqual((days["2026-10-27"]["status"], days["2026-10-27"]["shipped"], days["2026-10-27"]["overdue"]),
                         ("partial", 1, False))  # 오늘 납기는 아직 지나지 않음

    def test_due_soon(self):
        from .due_calendar import due_soon

        items = due_soon(today=self.TODAY)["items"]
        self.assertEqual([(i["po_no"], i["d_day"], i["status"]) for i in items],
                         [("26002", -7, "pending"), ("26003", 0, "partial"), ("26004", 9, "pending")])
        self.assertEqual(items[2]["quantity"], 2)

    def test_due_soon_api(self):
        res = self.client.get("/api/production/due-soon/")
        self.assertEqual((res.status_code, res.data["days"]), (200, 14))
        self.client.force_authenticate(User.objects.create_user("svc", password="x", view_teams=[S]))
        self.assertEqual(self.client.get("/api/production/due-soon/").status_code, 403)


class DueSearchTests(APITestCase):
    """납기 캘린더 검색: 모든 달에서 수주번호·판매처·사업명·일련번호로 찾기"""

    def setUp(self):
        self.client.force_authenticate(User.objects.create_user("viewer", password="x", role=User.Role.MEMBER,
                                                                view_teams=[P]))
        rows = [  # (일련번호, 납기일, 수주번호, 판매처, 사업명, 출고일)
            ("N82260001", date(2026, 3, 5), "26010", "가람상수도", "가상 정수장 사업", date(2026, 3, 3)),
            ("N82260002", date(2026, 3, 5), "26010", "가람상수도", "가상 정수장 사업", None),
            ("N82260003", date(2026, 11, 2), "26020", "나래발전", "가상 발전 사업", None),
            ("N82250004", date(2025, 7, 1), "25030", "가람상수도", "가상 배관 사업", date(2025, 6, 28)),
        ]
        for serial, due, po, customer, project, shipped in rows:
            ManufacturingRecord.objects.create(serial_full=serial, serial_short=serial[-4:], due_date=due, po_no=po,
                                               customer=customer, project_name=project, shipped_date=shipped)

    def search(self, q):
        return self.client.get("/api/production/due-calendar/search/", {"q": q})

    def test_search_by_customer_across_months_recent_first(self):
        res = self.search("가람")
        self.assertEqual(res.status_code, 200)
        self.assertEqual([(r["due_date"], r["po_no"]) for r in res.data["results"]],
                         [(date(2026, 3, 5), "26010"), (date(2025, 7, 1), "25030")])

    def test_search_by_po_with_hash_and_serial_shows_whole_order(self):
        self.assertEqual([r["po_no"] for r in self.search("#26020").data["results"]], ["26020"])
        order = self.search("N82260002").data["results"][0]  # 일련번호 하나로 찾아도 수주 묶음 전체
        self.assertEqual((order["po_no"], order["quantity"], order["shipped"], order["status"]), ("26010", 2, 1, "partial"))

    def test_search_by_project_and_empty_query(self):
        self.assertEqual([r["po_no"] for r in self.search("발전 사업").data["results"]], ["26020"])
        self.assertEqual(self.search("없는검색어").data["results"], [])
        self.assertEqual(self.search(" # ").status_code, 400)


class SalesSummaryTests(APITestCase):
    """specs/09-metrics.md 3절 판매량 (기준 날짜: 수주서 납기일)"""

    def setUp(self):
        from .models import SalesOrder, SalesOrderItem

        def order(no, industry, customer, due, items):
            o = SalesOrder.objects.create(sales_no=no, industry=industry, customer=customer, due_date=due,
                                          order_doc_no=no[-5:])
            for name, qty, flange in items:
                SalesOrderItem.objects.create(order=o, product_name=name, quantity=qty, flange=flange)

        order("NTK-SO-26006", "상하수도", "가람", date(2026, 10, 3), [("제수 150A", 3, "F10A"), ("제수 200A", 1, "")])
        order("NTK-SO-26007", "발전소", "다온", date(2026, 10, 9), [("제수 150A", 2, "F12")])
        order("NTK-SO-26008", "상하수도", "나래", date(2026, 11, 1), [("제수 150A", 9, "")])  # 11월 → 10월 집계 제외

    def test_rankings(self):
        from .metrics import sales_summary

        s = sales_summary(make_period("month", 2026, month=10))
        self.assertEqual(s["total"], 6)
        self.assertEqual(s["by_industry"], [{"name": "상하수도", "quantity": 4}, {"name": "발전소", "quantity": 2}])
        self.assertEqual(s["by_customer"][0], {"name": "가람", "quantity": 4})
        self.assertEqual(s["by_product"], [{"name": "제수 150A", "quantity": 5}, {"name": "제수 200A", "quantity": 1}])

    def test_quarter_includes_november(self):
        from .metrics import sales_summary

        self.assertEqual(sales_summary(make_period("quarter", 2026, quarter=4))["total"], 15)

    def test_flange_supplement_by_order_doc_no(self):
        from .serials import flanges_for

        record = ManufacturingRecord(serial_full="N82260001", po_no="26006")
        self.assertEqual(flanges_for(record), "F10A")
        self.assertIsNone(flanges_for(ManufacturingRecord(serial_full="N82260002", po_no="99999")))
