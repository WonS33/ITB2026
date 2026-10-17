from datetime import date

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

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
