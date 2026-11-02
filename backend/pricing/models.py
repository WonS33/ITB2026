"""제품 단가·원가 (specs/04-main-management.md 5절, specs/09-metrics.md 5절)

기업 제품 가격 계산표(원재료 → 판매가)를 기준값 몇 개와 모델별 원재료 가격으로 저장하고 나머지는 계산한다.
원가·마진·커미션은 대외비라 대표·관리자·경영지원팀만 보고(API에서도 확인), 실제 값은 로컬 DB에만 넣는다.
"""

from django.conf import settings
from django.db import models

from common.models import TimeStampedModel


class ProductPriceSetting(TimeStampedModel):
    """가격 계산 기준값 (적용일별로 한 줄 — 가장 최근 적용일을 쓴다)"""

    effective_date = models.DateField("적용일", unique=True)
    exchange_rate = models.DecimalField("환율(원/USD)", max_digits=10, decimal_places=2)
    customs_factor = models.DecimalField("통관 배수", max_digits=6, decimal_places=3)  # 원화 × 배수
    sga_rate = models.DecimalField("판관비율(%)", max_digits=6, decimal_places=2)  # 통관 후 × (1 + 비율)
    margin = models.DecimalField("마진 값", max_digits=5, decimal_places=3)  # 원가 ÷ 마진 값
    special_discount_rate = models.DecimalField("특별할인율(%)", max_digits=5, decimal_places=2)
    price_round_unit = models.PositiveIntegerField("판매가 올림 단위(원)", default=1000)
    commission_rate = models.DecimalField("커미션율(%)", max_digits=5, decimal_places=2)
    commission_unit = models.PositiveIntegerField("커미션 버림 단위(원)", default=10000)
    margin_choices = models.JSONField("마진 선택 목록", default=list, blank=True)  # 시뮬레이션에서 고르는 값
    # 화면에서 바꾼 기록 (2026-11-02): 누가(created_by, 공통 칸) 왜 바꿨는지. 계산표 파일로 넣은 줄은 비어 있다
    note = models.CharField("변경 사유", max_length=200, blank=True)

    class Meta:
        verbose_name = "제품 가격 기준값"
        verbose_name_plural = verbose_name
        ordering = ["-effective_date"]

    def __str__(self):
        return f"{self.effective_date} 기준값"

    @classmethod
    def current(cls):
        return cls.objects.order_by("-effective_date").first()


class PricingAccessLog(models.Model):
    """제품 단가·원가(대외비) 열람 기록 — 누가 언제 봤는지 (2026-11-02)

    시뮬레이션 값을 바꿀 때마다 API를 부르므로, 같은 사람은 10분에 한 번만 남긴다.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="사용자", on_delete=models.CASCADE, related_name="+")
    viewed_at = models.DateTimeField("열람 일시", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "제품 단가·원가 열람 기록"
        verbose_name_plural = verbose_name
        ordering = ["-viewed_at"]


class ProductModel(TimeStampedModel):
    """제품 모델별 원재료 가격(USD)과 커미션 계산용 판매금액"""

    model_name = models.CharField("모델", max_length=30, unique=True)  # 예: NTI-01
    series = models.CharField("시리즈", max_length=10)  # NTI / NTIT / NTIR
    assembly_usd = models.DecimalField("원재료 Assembly(USD)", max_digits=10, decimal_places=2)
    complete_usd = models.DecimalField("원재료 Complete(USD)", max_digits=10, decimal_places=2, null=True, blank=True)
    sale_price = models.PositiveIntegerField("판매금액(원, 커미션 계산용)", null=True, blank=True)
    sort_order = models.PositiveIntegerField("순서", default=0)

    class Meta:
        verbose_name = "제품 모델 가격"
        verbose_name_plural = verbose_name
        ordering = ["sort_order", "model_name"]

    def __str__(self):
        return self.model_name


class ProductOption(models.Model):
    """옵션 가격 (예: Modulating, Modbus) — 단위·더하는 단계는 확인 필요 (임시: USD, 원재료에 더함)"""

    name = models.CharField("옵션", max_length=50, unique=True)
    price_usd = models.DecimalField("가격(USD)", max_digits=10, decimal_places=2)
    sort_order = models.PositiveIntegerField("순서", default=0)

    class Meta:
        verbose_name = "제품 옵션 가격"
        verbose_name_plural = verbose_name
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name
