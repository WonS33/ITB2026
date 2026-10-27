from datetime import date

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APITestCase

from .periods import period_from_params, quarter_of

TODAY = date(2026, 10, 18)


class PeriodTests(SimpleTestCase):
    def test_month(self):
        p = period_from_params({"year": "2026", "period": "month", "month": "2"}, TODAY)
        self.assertEqual((p.start, p.end), (date(2026, 2, 1), date(2026, 2, 28)))
        self.assertEqual(p.month_count, 1)
        self.assertEqual(p.label, "2026년 2월")

    def test_leap_year_february(self):
        p = period_from_params({"year": "2028", "period": "month", "month": "2"}, TODAY)
        self.assertEqual(p.end, date(2028, 2, 29))

    def test_quarter_calendar_based(self):
        p = period_from_params({"year": "2026", "period": "quarter", "quarter": "4"}, TODAY)
        self.assertEqual((p.start, p.end), (date(2026, 10, 1), date(2026, 12, 31)))
        self.assertEqual(p.months, [10, 11, 12])
        self.assertEqual(p.label, "2026년 4분기")

    def test_year(self):
        p = period_from_params({"year": "2026", "period": "year"}, TODAY)
        self.assertEqual((p.start, p.end), (date(2026, 1, 1), date(2026, 12, 31)))
        self.assertEqual(p.month_count, 12)

    def test_defaults_to_today(self):
        p = period_from_params({}, TODAY)
        self.assertEqual((p.kind, p.year, p.months), ("month", 2026, [10]))
        q = period_from_params({"period": "quarter"}, TODAY)
        self.assertEqual(q.months, [10, 11, 12])

    def test_quarter_of(self):
        self.assertEqual([quarter_of(m) for m in (1, 3, 4, 6, 7, 9, 10, 12)], [1, 1, 2, 2, 3, 3, 4, 4])

    def test_invalid_values_raise_400(self):
        for params in ({"period": "week"}, {"month": "13"}, {"quarter": "0"}, {"year": "abc"}):
            with self.subTest(params=params), self.assertRaises(ValidationError):
                period_from_params(params, TODAY)


class PeriodYearsTests(APITestCase):
    """기간 선택 연도 범위: 가장 이른 데이터 연도 (2023년 이전 자료도 볼 수 있게)"""

    def test_earliest_year_follows_data(self):
        from datetime import date

        from accounts.models import User
        from production.models import ManufacturingRecord
        from service.models import TripReport

        self.client.force_authenticate(User.objects.create_user("u", password="x", view_teams=["service"]))
        self.assertIsNone(self.client.get("/api/periods/years/").data["earliest_year"])  # 데이터 없음
        ManufacturingRecord.objects.create(serial_full="N82190001", serial_short="0001", manufactured_date=date(2019, 5, 1))
        TripReport.objects.create(start_date=date(2021, 3, 2), requester="가상", region="서울특별시", paid_type="유상",
                                  author="가상")
        res = self.client.get("/api/periods/years/")
        self.assertEqual((res.status_code, res.data["earliest_year"]), (200, 2019))

    def test_login_required(self):
        self.assertEqual(self.client.get("/api/periods/years/").status_code, 401)
