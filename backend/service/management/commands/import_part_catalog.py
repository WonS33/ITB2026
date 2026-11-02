from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from service.catalog import parse_catalog
from service.models import PartCatalogItem, PartListPrice


class Command(BaseCommand):
    help = (
        "기업 부품 단가표 CSV(파트넘버·품명·적용 모델·기준단가)를 로컬 DB에 넣는다. "
        "실제 단가표는 대외비이므로 samples/ 폴더에만 두고, 배포 서버에서는 실행하지 않는다."
    )

    def add_arguments(self, parser):
        parser.add_argument("path", help="단가표 CSV 경로 (예: ../samples/부품 단가표.csv)")
        parser.add_argument("--dry-run", action="store_true", help="저장하지 않고 읽은 결과만 보여 준다")
        # 원본 단가표에 날짜가 없어 기준일을 따로 받는다 (정하지 않으면 임시 기준일 2026-11-01)
        parser.add_argument("--date", default="2026-11-01", help="단가표 기준일 YYYY-MM-DD (기본: 2026-11-01, 임시)")

    def handle(self, path, dry_run=False, **options):
        try:
            price_date = date.fromisoformat(options["date"])
        except ValueError:
            raise CommandError("--date는 YYYY-MM-DD 형식이어야 합니다.")
        file = Path(path)
        if not file.is_file():
            raise CommandError(f"파일이 없습니다: {file}")
        try:
            items, warnings = parse_catalog(file.read_bytes())
        except ValueError as e:
            raise CommandError(str(e))
        if not items:
            raise CommandError("파트넘버가 있는 줄을 찾지 못했습니다. 단가표 파일인지 확인해 주세요.")

        no_price = sum(1 for i in items if i["list_price"] is None)
        self.stdout.write(f"읽은 품목 {len(items)}개 (기준단가 없음 {no_price}개), 분류 {len({i['category'] for i in items})}개")
        for w in warnings:
            self.stdout.write(self.style.WARNING(f"확인 필요: {w}"))
        if dry_run:
            self.stdout.write("--dry-run: 저장하지 않았습니다.")
            return

        created = updated = changed = 0
        with transaction.atomic():
            for order, item in enumerate(items, start=1):
                # 파트넘버 + 품명이 같으면 갱신 (부품별로 정한 할인율·추가단가는 그대로 둔다)
                record, is_new = PartCatalogItem.objects.update_or_create(
                    part_no=item["part_no"], name=item["name"],
                    defaults={"category": item["category"], "applies_to": item["applies_to"], "sort_order": order},
                )
                # 단가표 개정 이력: 기준일마다 한 줄 (같은 기준일이면 고침, 예전 기준일 값은 지우지 않음)
                PartListPrice.objects.update_or_create(
                    item=record, effective_date=price_date, defaults={"list_price": item["list_price"]})
                latest = record.list_prices.order_by("-effective_date").first()  # 지금 기준값 = 가장 최근 기준일
                if not is_new and record.list_price != latest.list_price:
                    changed += 1
                record.list_price, record.list_price_date = latest.list_price, latest.effective_date
                record.save(update_fields=["list_price", "list_price_date", "updated_at"])
                created += is_new
                updated += not is_new
        keys = {(i["part_no"], i["name"]) for i in items}
        missing = [str(c) for c in PartCatalogItem.objects.all() if (c.part_no, c.name) not in keys]
        self.stdout.write(self.style.SUCCESS(
            f"새로 넣음 {created}개, 갱신 {updated}개 (단가표 기준일 {price_date}, 지금 기준단가가 바뀐 품목 {changed}개)"))
        self.stdout.write("예전 기준일의 기준단가는 개정 이력으로 남아, 예전 견적은 그때 단가표와 비교됩니다.")
        if missing:
            self.stdout.write(self.style.WARNING(f"이번 파일에 없는 기존 품목 {len(missing)}개 (지우지 않음): {', '.join(missing[:10])}"))
