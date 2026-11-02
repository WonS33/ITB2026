import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from service.models import PartCatalogItem, PartPrice

from .seed_service import REQUESTERS

# 출장지(업체)별 비교 화면을 볼 수 있게, 지금 단가표 부품에 **가상 출장지 단가**를 만든다.
# 업체는 가상 출장보고서의 가상 요청처, 단가는 단가표 기준단가에 무작위 비율(-10% ~ +25%)을 곱한 가상 값이다.
# 실제 견적이 아니므로 비고에 표시를 남기고, --clear로 이 표시가 있는 줄만 지운다.
MARKER = "가상 예시 단가 (seed_company_prices)"
COMPANIES = [name for name, _, _ in REQUESTERS]


class Command(BaseCommand):
    help = "단가표 부품에 가상 출장지(업체)별 단가 예시를 만든다 (--clear: 만든 예시만 지움)."

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="이 명령으로 만든 가상 예시 단가만 지운다")
        parser.add_argument("--seed", type=int, default=2026, help="무작위 값의 시작값 (같은 값이면 같은 예시)")
        parser.add_argument("--share", type=float, default=0.7, help="예시를 만들 부품 비율 (0~1, 기본 0.7)")

    def handle(self, *args, clear=False, seed=2026, share=0.7, **options):
        examples = PartPrice.objects.filter(quote_note=MARKER)
        if clear:
            deleted, _ = examples.delete()
            self.stdout.write(self.style.SUCCESS(f"가상 예시 단가 {deleted}줄을 지웠습니다."))
            return
        if examples.exists():
            self.stdout.write("가상 예시 단가가 이미 있습니다. 다시 만들려면 --clear 후 실행하세요.")
            return

        rng = random.Random(seed)
        items = [i for i in PartCatalogItem.objects.exclude(list_price=None) if rng.random() < share]
        start = date(2025, 7, 1)
        created = 0
        with transaction.atomic():
            for item in items:
                for company in rng.sample(COMPANIES, k=rng.randint(2, 5)):
                    # 업체마다 견적 1~2번 (두 번째는 더 나중 날짜 → 최근 단가로 비교됨)
                    days = sorted(rng.sample(range(0, 480), k=rng.randint(1, 2)))
                    for d in days:
                        price = round(item.list_price * rng.uniform(0.9, 1.25), -3)  # 천원 단위
                        PartPrice.objects.create(
                            part_name=item.name, catalog_item=item, quote_company=company,
                            effective_date=start + timedelta(days=d), unit_price=int(price),
                            quote_project="가상 예시", quote_note=MARKER,
                        )
                        created += 1
        self.stdout.write(self.style.SUCCESS(
            f"부품 {len(items)}개에 가상 출장지 단가 {created}줄을 만들었습니다 (업체 {len(COMPANIES)}곳 중 무작위)."))
