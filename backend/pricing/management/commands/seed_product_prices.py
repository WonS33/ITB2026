from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand

from pricing.models import ProductModel, ProductOption, ProductPriceSetting

# 개발·시연(배포 서버)용 **가상** 제품 가격 기준값과 모델. 실제 계산표가 아니다 (실제 값은 로컬 DB에만, CLAUDE.md 7절).
# 모델명은 실제 모델과 헷갈리지 않게 "VX"로 시작한다.
VIRTUAL_SETTING = {
    "exchange_rate": Decimal("1300"), "customs_factor": Decimal("1.2"), "sga_rate": Decimal("25"),
    "margin": Decimal("0.75"), "special_discount_rate": Decimal("3"), "commission_rate": Decimal("10"),
    "margin_choices": [0.6, 0.65, 0.7, 0.75, 0.8, 0.85],
}
VIRTUAL_MODELS = [
    # (모델, 시리즈, Assembly USD, Complete USD, 커미션 계산용 판매금액)
    ("VXA-01", "VXA", 500, 560, 2500000),
    ("VXA-02", "VXA", 650, 720, 3200000),
    ("VXA-03", "VXA", 900, 1000, None),
    ("VXB-01", "VXB", 400, 450, 2000000),
    ("VXB-02", "VXB", 1200, 1340, None),
]
VIRTUAL_OPTIONS = [("가상 옵션A", 150), ("가상 옵션B", 400)]


class Command(BaseCommand):
    help = "개발·시연용 가상 제품 가격 기준값·모델을 만든다 (기준값이 이미 있으면 아무것도 하지 않음)."

    def handle(self, *args, **options):
        if ProductPriceSetting.objects.exists():
            self.stdout.write("제품 가격 기준값이 이미 있어 가상 값을 만들지 않습니다.")
            return
        ProductPriceSetting.objects.create(effective_date=date(2026, 1, 1), **VIRTUAL_SETTING)
        for order, (name, series, assembly, complete, sale) in enumerate(VIRTUAL_MODELS, start=1):
            ProductModel.objects.create(model_name=name, series=series, assembly_usd=assembly, complete_usd=complete,
                                        sale_price=sale, sort_order=order)
        for order, (name, price) in enumerate(VIRTUAL_OPTIONS, start=1):
            ProductOption.objects.create(name=name, price_usd=price, sort_order=order)
        self.stdout.write(self.style.SUCCESS(f"가상 제품 {len(VIRTUAL_MODELS)}개와 기준값을 만들었습니다."))
