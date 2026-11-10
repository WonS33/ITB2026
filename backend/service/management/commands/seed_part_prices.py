from datetime import date

from django.core.management.base import BaseCommand

from service.models import PartCatalogItem, PartPrice

# 개발·시연(배포 서버)용 **가상** 부품 단가표와 출장지(업체)별 가상 단가. 실제 단가표·업체가 아니다.
# 실제 단가표는 대외비라 로컬 DB에만 import_part_catalog 명령으로 넣는다 (CLAUDE.md 7절).
# 파트넘버는 실제 번호와 헷갈리지 않게 "VX-"로 시작한다.
VIRTUAL_CATALOG = [
    # (파트넘버, 분류, 품명, 적용 모델, 기준단가)
    ("VX-01-A-00", "01 현장서비스", "가상 점검 출장", "", 300000),
    ("VX-01-B-00", "01 현장서비스", "가상 긴급 출장", "", 450000),
    ("VX-05-A-01", "05 MOTOR", "Motor", "NTI-01 ~ 03", 500000),
    ("VX-05-A-02", "05 MOTOR", "Motor", "NTI-04 ~ 05", 900000),
    ("VX-07-A-01", "07 BOARD", "Main Board", "NTI series", 900000),
    ("VX-07-B-01", "07 BOARD", "Power Board", "NTI-01 ~ 03", 500000),
    ("VX-09-B-01", "09 ELECTRONICS", "Magnetic Contactor", "NTI-01 ~ 05", 230000),
    ("VX-10-A-01", "10 ETC", "Limit Switch", "NTI series", None),  # 기준단가 미정 예시
]

# 업체(출장지)별 가상 단가: (파트넘버, 업체, 적용 시작일, 단가)
VIRTUAL_COMPANY_PRICES = [
    ("VX-01-A-00", "가상정수센터", date(2026, 3, 10), 300000),
    ("VX-01-A-00", "가상발전소", date(2026, 5, 2), 350000),
    ("VX-01-A-00", "가상플랜트", date(2026, 8, 20), 320000),
    ("VX-05-A-01", "가상정수센터", date(2026, 2, 15), 480000),
    ("VX-05-A-01", "가상발전소", date(2026, 6, 1), 560000),
    ("VX-05-A-01", "가상정수센터", date(2026, 9, 5), 500000),  # 같은 업체 재견적 → 최근 것만 비교에 씀
    ("VX-07-A-01", "가상가스", date(2026, 4, 12), 950000),
    ("VX-07-A-01", "가상플랜트", date(2026, 7, 7), 870000),
    ("VX-07-B-01", "가상발전소", date(2026, 1, 20), 520000),
    ("VX-09-B-01", "가상정수센터", date(2026, 3, 3), 240000),
    ("VX-09-B-01", "가상가스", date(2026, 5, 18), 230000),
    ("VX-09-B-01", "가상플랜트", date(2026, 10, 1), 260000),
]

# 예전(2026-10-20) 이 명령이 만들던 가상 단가 이력 — 업체·단가표 연결이 없다.
# 위 업체별 가상 단가와 섞이면 직전 대비 증감이 엉뚱하게 나오므로, 실행할 때 이 값과 똑같은 줄만 지운다
OLD_VIRTUAL_PRICES = {
    "Main Board": [(date(2025, 1, 1), 420000), (date(2025, 9, 1), 450000), (date(2026, 4, 1), 480000),
                   (date(2027, 1, 1), 495000)],
    "Power Board": [(date(2025, 3, 1), 280000), (date(2026, 3, 1), 300000)],
    "Magnetic Contactor": [(date(2025, 1, 1), 85000), (date(2025, 7, 1), 92000), (date(2026, 6, 1), 88000)],
    "Control PCB": [(date(2025, 5, 1), 350000)],
    "Limit Switch": [(date(2025, 1, 1), 45000), (date(2026, 1, 1), 48000)],
    "Motor": [(date(2025, 2, 1), 1200000), (date(2026, 2, 1), 1260000)],
}


class Command(BaseCommand):
    help = "개발·시연용 가상 부품 단가표와 업체별 가상 단가를 만든다 (단가표가 이미 있으면 아무것도 하지 않음)."

    def handle(self, *args, **options):
        self.remove_old_virtual_prices()
        # 실제 단가표(또는 사람이 넣은 단가표)를 덮어쓰지 않도록, 단가표가 하나라도 있으면 건너뛴다
        if PartCatalogItem.objects.exists():
            self.stdout.write("단가표가 이미 있어 가상 단가를 만들지 않습니다.")
            return
        items = {}
        for order, (part_no, category, name, applies_to, price) in enumerate(VIRTUAL_CATALOG, start=1):
            items[part_no] = PartCatalogItem.objects.create(
                part_no=part_no, category=category, name=name, applies_to=applies_to, list_price=price, sort_order=order)
        for part_no, company, effective_date, price in VIRTUAL_COMPANY_PRICES:
            item = items[part_no]
            PartPrice.objects.create(part_name=item.name, catalog_item=item, quote_company=company,
                                     effective_date=effective_date, unit_price=price)
        self.stdout.write(self.style.SUCCESS(
            f"가상 단가표 {len(VIRTUAL_CATALOG)}개, 업체별 가상 단가 {len(VIRTUAL_COMPANY_PRICES)}개를 만들었습니다."))

    def remove_old_virtual_prices(self):
        """예전 가상 단가 이력 지우기: 부품명·적용 시작일·단가가 모두 같고, 업체·단가표 연결·견적 번호가 없는 직접 입력 줄만"""
        removed = 0
        for part_name, prices in OLD_VIRTUAL_PRICES.items():
            for effective_date, unit_price in prices:
                removed += PartPrice.objects.filter(
                    part_name=part_name, effective_date=effective_date, unit_price=unit_price,
                    catalog_item=None, quote_company="", quote_no="", source=PartPrice.Source.MANUAL,
                ).delete()[0]
        if removed:
            self.stdout.write(f"예전 가상 단가 이력 {removed}줄을 지웠습니다.")
