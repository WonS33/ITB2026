"""제품 단가·원가 테스트 — 실제 계산표 값은 쓰지 않고 가상 숫자로만 확인한다 (CLAUDE.md 7절)"""

import os
import tempfile
from datetime import date
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.test import APITestCase

from accounts.models import User

from .engine import compute_commission, compute_steps, parse_data_sheet, parse_product_sheet, verify
from .models import ProductModel, ProductOption, ProductPriceSetting

SETTING = {"exchange_rate": Decimal("1000"), "customs_factor": Decimal("1.2"), "sga_rate": Decimal("25"),
           "margin": Decimal("0.8"), "special_discount_rate": Decimal("5")}

# 가상 계산표: 원재료 100 USD → 원화 100,000 → 통관 120,000 → 원가 150,000 → 마진 반영 187,500 → 판매가 188,000
#             → 특별할인 178,600 → 179,000(올림)
PRODUCT_CSV = (
    "모델,원가,,,,,판매가,,\n,원재료,,,통관,판관비,마진,기타,특별할인\n,USD,KRW,옵션,,,,,\n"
    ',Assembly," 1,000 ", N/A ,1.2,25%,0.8, 금액작성 ,5%\n'
    'VXA-01, 100 ," 100,000 "," 100,000 "," 120,000 "," 150,000 "," 187,500 "," 188,000 "," 179,000 "\n'
)
DATA_CSV = (
    ",Complete,Assembly,,마진,,옵션,가격\n"
    "VXA-01, 110 , 100 ,,0.70,,N/A,0\n"
    "VXA-02, 220 , 200 ,,0.80,,가상옵션,50\n"
)


class EngineTests(APITestCase):
    def test_steps(self):
        s = compute_steps(100, **SETTING)
        self.assertEqual([int(s[k]) for k in ("krw", "with_option", "customs", "cost")], [100000, 100000, 120000, 150000])
        self.assertEqual(s["margin_price"], Decimal("187500"))
        self.assertEqual((s["sale_price"], s["special_price"]), (188000, 179000))  # 천원 단위 올림

    def test_option_added_before_customs(self):
        s = compute_steps(100, option_usd=Decimal(50), **SETTING)
        self.assertEqual(int(s["with_option"]), 150000)  # 옵션 50 USD × 환율

    def test_commission_floors_to_unit(self):
        c = compute_commission(300000, Decimal("187500"), commission_rate=Decimal(15))
        # 이익 112,500 / 커미션 45,000 → 만원 미만 버림 40,000 / 차감 72,500 / 마진율 24.2%
        self.assertEqual((c["profit"], c["commission"], c["net_profit"], c["margin_rate"]), (112500, 40000, 72500, 24.2))

    def test_parse_and_verify(self):
        setting, models = parse_product_sheet(PRODUCT_CSV.encode("utf-8"))
        self.assertEqual(setting, SETTING | {"exchange_rate": Decimal("1000")})
        self.assertEqual((models[0]["model_name"], models[0]["series"], models[0]["assembly_usd"]), ("VXA-01", "VXA", 100))
        commissions = [{"model_name": "VXA-01", "sale_amount": Decimal(300000), "file": {
            "supply_price": Decimal(187500), "profit": Decimal(112500), "commission": Decimal(40000), "net_profit": Decimal(72500)}}]
        self.assertEqual(verify(setting, models, commissions, commission_rate=15), [])
        models[0]["file"]["sale_price"] = Decimal(189000)  # 파일 금액이 계산과 다르면 찾아냄
        self.assertEqual(verify(setting, models, commissions, commission_rate=15), ["VXA-01 판매가"])

    def test_parse_data_sheet(self):
        usd, margins, options = parse_data_sheet(DATA_CSV.encode("utf-8"))
        self.assertEqual(usd["VXA-02"], {"complete_usd": 220, "assembly_usd": 200})
        self.assertEqual(margins, [0.7, 0.8])
        self.assertEqual(options, [{"name": "가상옵션", "price_usd": 50}])  # N/A(옵션 없음)는 뺌


class ImportCommandTests(APITestCase):
    def write(self, content):
        f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
        f.write(content)
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def run_import(self, commission_csv):
        call_command("import_product_prices", product=self.write(PRODUCT_CSV), data=self.write(DATA_CSV),
                     commission=self.write(commission_csv), stdout=open(os.devnull, "w"))

    def test_import_saves_when_verified(self):
        self.run_import('제품,판매금액,원가,이익,커미션(15%),커미션 차감이익,마진율\n'
                        'VXA-01," 300,000 "," 187,500 "," 112,500 "," 40,000 "," 72,500 ",\n')
        setting = ProductPriceSetting.current()
        self.assertEqual((setting.effective_date, setting.exchange_rate, setting.commission_rate),
                         (date(2026, 11, 1), 1000, 15))
        model = ProductModel.objects.get()
        self.assertEqual((model.complete_usd, model.sale_price), (110, 300000))

    def test_import_refuses_mismatch(self):
        with self.assertRaises(CommandError):
            self.run_import('제품,판매금액,원가,이익,커미션(15%),커미션 차감이익,마진율\n'
                            'VXA-01," 300,000 "," 187,500 "," 112,500 "," 50,000 "," 62,500 ",\n')  # 커미션이 규칙과 다름
        self.assertFalse(ProductPriceSetting.objects.exists())  # 아무것도 저장하지 않음


class PricingApiTests(APITestCase):
    def setUp(self):
        ProductPriceSetting.objects.create(effective_date=date(2026, 1, 1), commission_rate=15,
                                           margin_choices=[0.7, 0.8], **SETTING)
        ProductModel.objects.create(model_name="VXA-01", series="VXA", assembly_usd=100, complete_usd=110,
                                    sale_price=300000, sort_order=1)
        ProductModel.objects.create(model_name="VXB-01", series="VXB", assembly_usd=200, sort_order=2)
        ProductOption.objects.create(name="가상옵션", price_usd=50)

    def login(self, role, view=(), edit=()):
        self.client.force_authenticate(User.objects.create_user(
            f"u{User.objects.count()}", password="x", role=role, view_teams=list(view), edit_teams=list(edit)))

    def test_only_full_access(self):
        self.login(User.Role.LEADER, [User.Team.SERVICE], [User.Team.SERVICE])
        self.assertEqual(self.client.get("/api/pricing/products/").status_code, 403)
        self.assertEqual(self.client.get("/api/pricing/commission/?model=VXA-01&sale_amount=1").status_code, 403)
        self.login(User.Role.LEADER, [User.Team.PRODUCTION], [User.Team.PRODUCTION])
        self.assertEqual(self.client.get("/api/pricing/products/").status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/pricing/products/").status_code, 401)

    def test_products_and_commission(self):
        self.login(User.Role.ADMIN)
        res = self.client.get("/api/pricing/products/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Cache-Control"], "no-store")
        first = res.data["models"][0]
        self.assertEqual((first["steps"]["sale_price"], first["change"]), (188000, 0))
        self.assertFalse(res.data["simulation"]["active"])
        self.assertEqual(res.data["series"], ["VXA", "VXB"])  # 시리즈 목록은 중복 없이
        self.assertEqual(res.data["commissions"][0]["commission"], 40000)
        calc = self.client.get("/api/pricing/commission/?model=VXA-01&sale_amount=400000").data
        self.assertEqual((calc["profit"], calc["commission"]), (212500, 60000))

    def test_simulation_does_not_save(self):
        self.login(User.Role.ADMIN)
        res = self.client.get("/api/pricing/products/?exchange_rate=1100&base=complete&option=가상옵션")
        self.assertTrue(res.data["simulation"]["active"])
        first, second = res.data["models"]
        # Complete 110 + 옵션 50 = 160 USD × 1,100 = 176,000 → 통관 211,200 → 원가 264,000 → 마진 330,000
        self.assertEqual(first["steps"]["sale_price"], 330000)
        self.assertEqual(first["change"], 330000 - 188000)
        self.assertIsNone(second["steps"])  # Complete 가격이 없는 모델
        self.assertEqual(ProductPriceSetting.current().exchange_rate, 1000)  # 저장된 값은 그대로
        self.assertEqual(self.client.get("/api/pricing/products/?margin=0").status_code, 400)
        self.assertEqual(self.client.get("/api/pricing/products/?option=없는옵션").status_code, 400)

    def test_management_member_can_view(self):
        self.login(User.Role.MEMBER, [User.Team.MANAGEMENT])
        self.assertEqual(self.client.get("/api/pricing/products/").status_code, 200)


class SettingChangeAndAccessLogTests(APITestCase):
    """화면에서 기준값 바꾸기·변경 기록, 대외비 열람 기록 (2026-11-02)"""

    def setUp(self):
        ProductPriceSetting.objects.create(effective_date=date(2026, 1, 1), commission_rate=15,
                                           margin_choices=[0.7, 0.8], **SETTING)
        ProductModel.objects.create(model_name="VXA-01", series="VXA", assembly_usd=100, sort_order=1)
        self.admin = User.objects.create_user("boss", password="x", role=User.Role.ADMIN)
        self.client.force_authenticate(self.admin)

    def body(self, **changes):
        return {"effective_date": "2026-03-01", "note": "환율 반영", **{k: str(v) for k, v in SETTING.items()},
                "commission_rate": "15", **changes}

    def test_change_creates_new_setting_with_history(self):
        res = self.client.post("/api/pricing/settings/", self.body(exchange_rate="1100"), format="json")
        self.assertEqual(res.status_code, 200)
        latest = res.data["settings"][0]
        self.assertEqual((latest["exchange_rate"], latest["created_by"], latest["note"]), (1100.0, "boss", "환율 반영"))
        self.assertEqual(latest["changes"], [{"label": "환율", "old": 1000.0, "new": 1100.0}])
        self.assertEqual(res.data["settings"][1]["created_by"], "계산표 파일")  # 예전 값은 기록으로 남음
        self.assertEqual(ProductPriceSetting.current().exchange_rate, 1100)
        self.assertEqual(ProductPriceSetting.current().margin_choices, [0.7, 0.8])  # 바꾸지 않는 값은 이어 씀
        # 그다음 계산은 새 기준값으로: 100 USD × 1,100 = 110,000 → 132,000 → 165,000 → 206,250 → 207,000
        self.assertEqual(self.client.get("/api/pricing/products/").data["models"][0]["steps"]["sale_price"], 207000)

    def test_change_validation(self):
        self.assertEqual(self.client.post("/api/pricing/settings/", self.body(), format="json").status_code, 400)  # 바뀐 값 없음
        self.assertEqual(self.client.post("/api/pricing/settings/", self.body(exchange_rate="1100", effective_date="2025-12-01"),
                                          format="json").status_code, 400)  # 지금 적용일보다 이전
        self.assertEqual(self.client.post("/api/pricing/settings/", self.body(exchange_rate="1100", effective_date="2099-01-01"),
                                          format="json").status_code, 400)  # 미래
        self.client.force_authenticate(User.objects.create_user(
            "svc", password="x", role=User.Role.LEADER, view_teams=[User.Team.SERVICE], edit_teams=[User.Team.SERVICE]))
        self.assertEqual(self.client.post("/api/pricing/settings/", self.body(exchange_rate="1100"), format="json").status_code, 403)
        self.assertEqual(self.client.get("/api/pricing/access-log/").status_code, 403)

    def test_access_log_once_per_10_minutes(self):
        self.client.get("/api/pricing/products/")
        self.client.get("/api/pricing/products/?exchange_rate=1200")  # 시뮬레이션은 다시 남기지 않음
        logs = self.client.get("/api/pricing/access-log/").data["logs"]
        self.assertEqual([(log["user"], log["role"]) for log in logs], [("boss", User.Role.ADMIN.label)])


class SeedTests(APITestCase):
    def test_seed_is_virtual_and_idempotent(self):
        from .management.commands.seed_product_prices import VIRTUAL_MODELS

        self.assertTrue(all(m[0].startswith("VX") for m in VIRTUAL_MODELS))
        call_command("seed_product_prices", stdout=open(os.devnull, "w"))
        call_command("seed_product_prices", stdout=open(os.devnull, "w"))
        self.assertEqual(ProductModel.objects.count(), len(VIRTUAL_MODELS))
        self.assertEqual(ProductPriceSetting.objects.count(), 1)
