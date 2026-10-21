from datetime import date

from django.core.management.base import BaseCommand

from service.models import PartPrice

# 개발·시연용 가상 부품 단가 이력 (실제 단가 아님). 부품명은 seed_service의 가상 부품과 같다.
# 증가·감소·변동 없음·적용 예정(미래 날짜)을 모두 볼 수 있게 골고루 만든다.
VIRTUAL_PRICES = {
    "Main Board": [(date(2025, 1, 1), 420000), (date(2025, 9, 1), 450000), (date(2026, 4, 1), 480000),
                   (date(2027, 1, 1), 495000)],
    "Power Board": [(date(2025, 3, 1), 280000), (date(2026, 3, 1), 300000)],
    "Magnetic Contactor": [(date(2025, 1, 1), 85000), (date(2025, 7, 1), 92000), (date(2026, 6, 1), 88000)],
    "Control PCB": [(date(2025, 5, 1), 350000)],
    "Limit Switch": [(date(2025, 1, 1), 45000), (date(2026, 1, 1), 48000)],
    "Motor": [(date(2025, 2, 1), 1200000), (date(2026, 2, 1), 1260000)],
}


class Command(BaseCommand):
    help = "개발·시연용 가상 부품 단가 이력을 만든다 (이미 단가가 있는 부품은 건드리지 않음)."

    def handle(self, *args, **options):
        created, skipped = 0, []
        for part_name, prices in VIRTUAL_PRICES.items():
            # 사람이 직접 입력한 단가를 덮어쓰지 않도록, 단가가 하나라도 있는 부품은 건너뛴다
            if PartPrice.objects.filter(part_name=part_name).exists():
                skipped.append(part_name)
                continue
            for effective_date, unit_price in prices:
                PartPrice.objects.create(part_name=part_name, unit_price=unit_price, effective_date=effective_date)
                created += 1
        self.stdout.write(f"가상 부품 단가: {created}줄 생성")
        if skipped:
            self.stdout.write(f"이미 단가가 있어 건너뜀: {', '.join(skipped)}")
