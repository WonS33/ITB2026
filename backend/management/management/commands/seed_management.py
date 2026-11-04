import random
from datetime import date, datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from management.models import AnnualSalesTarget, ExpenseCategory, LedgerEntry, MonthlyFinance, OtherExpense

# 개발·시연용 가상 데이터 (조원 저장소 prisma/seed.ts 의 값 범위를 따름, 실제 기업 숫자 아님)
CATEGORIES = [
    # 이름, 비용 성격, 월 금액 범위(원)
    ("광고선전비", ExpenseCategory.CostType.FIXED, 1_000_000, 5_000_000),
    ("접대비", ExpenseCategory.CostType.FIXED, 500_000, 3_000_000),
    ("복리후생비", ExpenseCategory.CostType.FIXED, 2_000_000, 4_000_000),
    ("차량유지비", ExpenseCategory.CostType.FIXED, 800_000, 1_500_000),
    ("지급수수료", "", 300_000, 1_000_000),  # 고정/변동 미분류 예시
]
MONTHS = 24
LEDGER_MONTHS = 3  # 장부 가상 데이터는 최근 3개월만
# 연간 목표 (올해 기준 몇 년 전, 연간 목표, 1~4분기 목표 — None = 자동 배분). 분기 배분 규칙 세 가지를 모두 보여 줌
TARGETS = [
    (2, 2_200_000_000, [None, None, None, 600_000_000]),  # 4분기만 입력 → 나머지는 자동 배분
    (1, 2_400_000_000, [500_000_000, 600_000_000, 600_000_000, 700_000_000]),  # 모두 입력
    (0, 2_800_000_000, [None, None, None, None]),  # 모두 비움 → 연간 ÷ 4
]
HEADCOUNT = 12  # 직원 수 (프로젝트 개요: 직원 12명)


def won(rng, low, high):
    """low~high 원 사이 금액, 천 원 단위"""
    return round(rng.uniform(low, high) / 1000) * 1000


class Command(BaseCommand):
    help = "가상 경영지원 데이터: 최근 3년 연간 목표 + 그 외 지출 항목 5개 + 지난달까지 24개월 월별 실적 (지난달만 임시저장) + 최근 3개월 경영지원 관리 장부. 여러 번 실행해도 같은 값으로 덮어씀."

    def handle(self, *args, **options):
        rng = random.Random(20261016)  # 실행할 때마다 같은 가상 값
        categories = []
        for order, (name, cost_type, low, high) in enumerate(CATEGORIES, start=1):
            category, _ = ExpenseCategory.objects.update_or_create(
                name=name, defaults={"cost_type": cost_type, "sort_order": order, "is_active": True}
            )
            categories.append((category, low, high))

        today = timezone.localdate()
        for years_ago, amount, quarters in TARGETS:
            AnnualSalesTarget.objects.update_or_create(
                year=today.year - years_ago,
                defaults={
                    "target_amount": amount,
                    **{f"q{i}_target": q for i, q in enumerate(quarters, start=1)},
                    "headcount": HEADCOUNT,
                },
            )

        last = today.year * 12 + today.month - 2  # 지난달 (0부터 센 월 번호)
        for i in range(MONTHS):
            index = last - (MONTHS - 1) + i
            year, month = index // 12, index % 12 + 1
            is_last = i == MONTHS - 1
            growth = 1 - (MONTHS - 1 - i) * 0.008  # 조금씩 커지는 회사처럼
            product = won(rng, 140_000_000 * growth, 220_000_000 * growth)
            merchandise = won(rng, 18_000_000 * growth, 40_000_000 * growth)
            next_month = date(year + (month == 12), month % 12 + 1, 5)
            finance, _ = MonthlyFinance.objects.update_or_create(
                year=year,
                month=month,
                defaults={
                    "product_sales": product,
                    "merchandise_sales": merchandise,
                    "service_sales": won(rng, 8_000_000 * growth, 25_000_000 * growth),
                    "merchandise_purchase": merchandise * 70 // 100,
                    "material_purchase": product * rng.randint(35, 45) // 100,
                    "expense": won(rng, 25_000_000 * growth, 38_000_000 * growth),
                    "cash_balance": 150_000_000 + i * 4_500_000,
                    "status": MonthlyFinance.Status.DRAFT if is_last else MonthlyFinance.Status.CONFIRMED,
                    # 확정 일시: 다음 달 5일
                    "confirmed_at": None if is_last else timezone.make_aware(datetime.combine(next_month, datetime.min.time())),
                },
            )
            for category, low, high in categories:
                OtherExpense.objects.update_or_create(
                    monthly=finance, category=category, defaults={"amount": won(rng, low, high)}
                )

        ledger_rows = self.seed_ledger(rng, last)

        first = last - (MONTHS - 1)
        self.stdout.write(
            f"그 외 지출 항목 {len(categories)}개, 월별 실적 {first // 12}-{first % 12 + 1:02d} ~ "
            f"{last // 12}-{last % 12 + 1:02d} ({MONTHS}개월, 마지막 달은 임시저장), "
            f"경영지원 관리 장부 최근 {LEDGER_MONTHS}개월 {ledger_rows}행"
        )

    def seed_ledger(self, rng, last):
        """경영지원 관리 장부: 최근 몇 달, 블록 4개 (가상 거래처 — 이름 끝 "(가상)" 으로 구분해 다시 만듦)"""
        K, P, X = LedgerEntry.Kind, LedgerEntry.PurchaseType, LedgerEntry.ExpenseType
        count = 0
        for index in range(last - LEDGER_MONTHS + 1, last + 1):
            year, month = index // 12, index % 12 + 1
            LedgerEntry.objects.filter(year=year, month=month, partner_name__endswith="(가상)").delete()
            rows = [
                (K.AR, {"ar_status": LedgerEntry.ArStatus.LONG_OVERDUE, "partner_code": "0000000087"}, "가나상사(가상)", 12_500_000, 13_000_000),
                (K.AR, {"ar_status": LedgerEntry.ArStatus.SCHEDULED, "partner_code": "0000000215"}, "마바플랜트(가상)", 8_000_000, 30_000_000),
                (K.AP, {"purchase_type": P.RAW_MATERIAL}, "사아금속(가상)", 30_000_000, 50_000_000),
                (K.AP, {"purchase_type": P.RAW_MATERIAL}, "자차주물(가상)", 10_000_000, 20_000_000),
                (K.AP, {"purchase_type": P.GOODS}, "카타무역(가상)", 15_000_000, 30_000_000),
                (K.AP, {}, "파하부품(가상)", 1_000_000, 3_000_000),  # 매입유형 빈 행 (넣을 칸을 사람이 고름)
                (K.ACCRUED_STAFF, {}, "직원 경비 합계(가상)", 25_000_000, 35_000_000),
                (K.ACCRUED_VENDOR, {"expense_type": X.ADVERTISING}, "가람광고(가상)", 1_000_000, 4_000_000),
                (K.ACCRUED_VENDOR, {"expense_type": X.ENTERTAINMENT}, "나래식당(가상)", 500_000, 2_500_000),
                (K.ACCRUED_VENDOR, {"expense_type": X.OTHER, "auto_transfer": True}, "다온통신(가상)", 150_000, 200_000),
            ]
            for kind, extra, name, low, high in rows:
                LedgerEntry.objects.create(
                    year=year, month=month, kind=kind, partner_name=name, amount=won(rng, low, high), **extra
                )
                count += 1
        return count
