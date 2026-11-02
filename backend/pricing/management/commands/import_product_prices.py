from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from pricing.engine import parse_commission_sheet, parse_data_sheet, parse_product_sheet, verify
from pricing.models import ProductModel, ProductOption, ProductPriceSetting


class Command(BaseCommand):
    help = (
        "기업 제품 가격 계산표(제품·선택 목록·커미션 CSV 3개)를 로컬 DB에 넣는다. "
        "파일의 금액과 다시 계산한 금액이 다르면 저장하지 않는다. 대외비 자료라 배포 서버에서는 실행하지 않는다."
    )

    def add_arguments(self, parser):
        parser.add_argument("--product", required=True, help="제품 계산표 CSV (원재료 → 판매가)")
        parser.add_argument("--data", required=True, help="선택 목록 CSV (Complete·Assembly, 마진, 옵션)")
        parser.add_argument("--commission", required=True, help="커미션 CSV (판매금액·원가·이익·커미션)")
        parser.add_argument("--date", default="2026-11-01", help="기준값 적용일 YYYY-MM-DD (기본: 2026-11-01, 임시)")
        parser.add_argument("--commission-rate", default="15", help="커미션율(%%) — 파일 머리글 기준 15")
        parser.add_argument("--dry-run", action="store_true", help="검산만 하고 저장하지 않는다")

    def read(self, path):
        file = Path(path)
        if not file.is_file():
            raise CommandError(f"파일이 없습니다: {file}")
        return file.read_bytes()

    def handle(self, *args, **o):
        try:
            effective = date.fromisoformat(o["date"])
            setting, models = parse_product_sheet(self.read(o["product"]))
            usd, margins, options = parse_data_sheet(self.read(o["data"]))
            commissions = parse_commission_sheet(self.read(o["commission"]))
        except ValueError as e:
            raise CommandError(str(e))
        if not models:
            raise CommandError("제품 계산표에서 모델 줄을 찾지 못했습니다.")

        problems = verify(setting, models, commissions, commission_rate=o["commission_rate"])
        mismatched = [m["model_name"] for m in models
                      if m["model_name"] in usd and usd[m["model_name"]]["assembly_usd"] != m["assembly_usd"]]
        if mismatched:
            problems.append(f"두 파일의 Assembly 원재료 가격이 다른 모델: {', '.join(mismatched)}")
        self.stdout.write(f"모델 {len(models)}개, 옵션 {len(options)}개, 마진 선택 {len(margins)}개, 커미션 {len(commissions)}개")
        if problems:
            for p in problems:
                self.stdout.write(self.style.ERROR(f"검산 불일치: {p}"))
            raise CommandError("파일 금액과 계산 결과가 달라 저장하지 않았습니다. 계산 규칙(pricing/engine.py)이나 파일을 확인해 주세요.")
        self.stdout.write(self.style.SUCCESS("검산 통과: 모든 모델의 단계별 금액과 커미션이 계산 규칙과 일치합니다."))
        if o["dry_run"]:
            self.stdout.write("--dry-run: 저장하지 않았습니다.")
            return

        sale_amounts = {c["model_name"]: c["sale_amount"] for c in commissions}
        with transaction.atomic():
            ProductPriceSetting.objects.update_or_create(effective_date=effective, defaults={
                **setting, "commission_rate": o["commission_rate"], "margin_choices": margins})
            for order, m in enumerate(models, start=1):
                ProductModel.objects.update_or_create(model_name=m["model_name"], defaults={
                    "series": m["series"], "assembly_usd": m["assembly_usd"],
                    "complete_usd": usd.get(m["model_name"], {}).get("complete_usd"),
                    "sale_price": sale_amounts.get(m["model_name"]), "sort_order": order})
            for order, opt in enumerate(options, start=1):
                ProductOption.objects.update_or_create(name=opt["name"], defaults={"price_usd": opt["price_usd"],
                                                                                   "sort_order": order})
        self.stdout.write(self.style.SUCCESS(f"저장했습니다 (기준값 적용일 {effective})."))
