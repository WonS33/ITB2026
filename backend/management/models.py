"""경영지원팀 데이터 (specs/07-data-model.md 2절)

조원 저장소(yeonk-rgb/newtork-dashboard)의 prisma/schema/management.prisma 를 Django 모델로 옮겼다 (2026-11-04).
- 금액은 모두 원 단위 정수
- 월별 실적은 임시저장(draft) / 확정(confirmed) 두 상태. 대시보드에는 확정된 달만 반영한다
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from common.models import TimeStampedModel


class MonthlyFinance(TimeStampedModel):
    """월별 실적 (연도+월 하나에 한 줄)"""

    class Status(models.TextChoices):
        DRAFT = "draft", "임시저장"
        CONFIRMED = "confirmed", "확정"

    year = models.PositiveSmallIntegerField("연도")
    month = models.PositiveSmallIntegerField("월")  # 1~12

    product_sales = models.PositiveBigIntegerField("제품 매출액", default=0)
    merchandise_sales = models.PositiveBigIntegerField("상품 매출액", default=0)
    service_sales = models.PositiveBigIntegerField("용역 매출액", default=0)
    merchandise_purchase = models.PositiveBigIntegerField("상품 매입액", default=0)
    material_purchase = models.PositiveBigIntegerField("원재료 매입액", default=0)
    expense = models.PositiveBigIntegerField("경비 지출액", default=0)
    # 선택 칸: 비우면 null (0원과 다름). 매출·지출 합계에는 넣지 않는다
    cash_balance = models.PositiveBigIntegerField("월말 통장 잔액", null=True, blank=True)

    status = models.CharField("상태", max_length=10, choices=Status.choices, default=Status.DRAFT)
    confirmed_at = models.DateTimeField("확정 일시", null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="마지막 수정자",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = "월별 실적"
        verbose_name_plural = verbose_name
        ordering = ["year", "month"]
        constraints = [models.UniqueConstraint(fields=["year", "month"], name="unique_monthly_finance")]

    def __str__(self):
        return f"{self.year}년 {self.month}월 ({self.get_status_display()})"


class ExpenseCategory(models.Model):
    """"그 외 지출" 항목 (예: 광고선전비, 접대비). 항목 관리는 목표·항목 설정 화면에서 한다"""

    class CostType(models.TextChoices):
        FIXED = "fixed", "고정비"
        VARIABLE = "variable", "변동비"

    name = models.CharField("항목 이름", max_length=30, unique=True)
    cost_type = models.CharField("비용 성격", max_length=10, choices=CostType.choices, blank=True)
    # False면 새 입력 화면에서 숨김 (과거 데이터는 그대로)
    is_active = models.BooleanField("사용 중", default=True)
    sort_order = models.PositiveSmallIntegerField("순서", default=0)

    class Meta:
        verbose_name = "그 외 지출 항목"
        verbose_name_plural = verbose_name
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name


class OtherExpense(models.Model):
    """월별 "그 외 지출" 금액 (항목마다 한 줄)"""

    monthly = models.ForeignKey(MonthlyFinance, on_delete=models.CASCADE, related_name="other_expenses")
    # 금액이 있는 항목은 지울 수 없다 (비활성화만)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name="+")
    amount = models.PositiveBigIntegerField("금액", default=0)

    class Meta:
        verbose_name = "그 외 지출"
        verbose_name_plural = verbose_name
        constraints = [models.UniqueConstraint(fields=["monthly", "category"], name="unique_other_expense")]


class LedgerEntry(TimeStampedModel):
    """경영지원 관리 장부 (채권·채무): 기준년월별 거래처 잔액 — 고객사 「경영지원_관리」 엑셀의 블록 4개

    월간 입력의 [경영지원 관리에서 불러오기]가 외상매입금·미지급비용(직원·업체)을 읽는다.
    (장부를 고치는 화면은 아직 옮기지 않음 — 지금은 가상 데이터·Django 관리 화면으로만 넣는다)
    """

    class Kind(models.TextChoices):
        AR = "ar", "외상매출금"
        AP = "ap", "외상매입금"
        ACCRUED_STAFF = "accrued_staff", "미지급비용-직원"
        ACCRUED_VENDOR = "accrued_vendor", "미지급비용-업체"

    class ArStatus(models.TextChoices):
        LONG_OVERDUE = "long_overdue", "장기 미수금"
        COLLECTED = "collected", "당월 수금"
        SCHEDULED = "scheduled", "당월 수금예정"

    class PurchaseType(models.TextChoices):
        GOODS = "goods", "상품매입"
        RAW_MATERIAL = "raw_material", "원재료매입"

    class ExpenseType(models.TextChoices):
        ADVERTISING = "advertising", "광고선전비"
        ENTERTAINMENT = "entertainment", "접대비"
        OTHER = "other", "기타"

    year = models.PositiveSmallIntegerField("연도")
    month = models.PositiveSmallIntegerField("월")
    kind = models.CharField("구분", max_length=20, choices=Kind.choices)
    ar_status = models.CharField("상태(외상매출금)", max_length=20, choices=ArStatus.choices, blank=True)
    purchase_type = models.CharField("매입유형(외상매입금)", max_length=20, choices=PurchaseType.choices, blank=True)
    expense_type = models.CharField("비용유형(미지급비용-업체)", max_length=20, choices=ExpenseType.choices, blank=True)
    auto_transfer = models.BooleanField("자동이체(미지급비용-업체)", default=False)
    partner_code = models.CharField("거래처코드", max_length=10, blank=True)  # 숫자 10자리 글자 (앞자리 0 유지)
    partner_name = models.CharField("거래처명", max_length=100)
    amount = models.BigIntegerField("잔액")  # 장부 금액은 부가세 포함
    note = models.CharField("적요", max_length=200, blank=True)
    due_on = models.DateField("예정일", null=True, blank=True)
    settled_on = models.DateField("완료일", null=True, blank=True)
    # 숨김(삭제 대신) — 값이 있으면 불러오기·집계에서 뺀다
    deleted_at = models.DateTimeField("숨긴 일시", null=True, blank=True)

    class Meta:
        verbose_name = "경영지원 관리 장부"
        verbose_name_plural = verbose_name
        ordering = ["year", "month", "kind", "id"]
        indexes = [models.Index(fields=["year", "month", "kind"])]

    def __str__(self):
        return f"{self.year}-{self.month:02d} {self.get_kind_display()} · {self.partner_name}"


class AuditLog(models.Model):
    """변경 기록 (누가 언제 무엇을 바꿨는지). 한 번 넣은 기록은 고치거나 지울 수 없다.

    - 바뀐 칸은 화면 표기 그대로의 글자로 남긴다 (예: "12,500,000원")
    - 사용자를 지워도 기록이 남도록 그때 아이디(actor_username)를 함께 저장
    - 비밀번호·토큰 같은 칸은 기록하지 않는다 (audit.py 에서 거부)
    """

    occurred_at = models.DateTimeField("일시", default=timezone.now, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="사용자", on_delete=models.SET_NULL, null=True, related_name="+"
    )
    actor_username = models.CharField("그때 아이디", max_length=150)
    area = models.CharField("영역", max_length=20, default="management")
    screen = models.CharField("화면", max_length=40, db_index=True)  # 예: entry, entry-export
    action = models.CharField("동작", max_length=30)  # 예: CONFIRM, UNCONFIRM, EXPORT
    target_type = models.CharField("대상 종류", max_length=40)
    target_id = models.CharField("대상 id", max_length=64)
    target_label = models.CharField("대상 이름", max_length=200)  # 예: "2026년 10월 월간 입력"
    changes = models.JSONField("바뀐 칸", default=list)  # [{field, label, before, after}]
    meta = models.JSONField("추가 정보", null=True, blank=True)  # 다운로드 기간·파일 이름 등

    class Meta:
        verbose_name = "변경 기록"
        verbose_name_plural = verbose_name
        ordering = ["-occurred_at", "-id"]
        indexes = [models.Index(fields=["target_type", "target_id"])]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError("변경 기록은 고칠 수 없습니다.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("변경 기록은 지울 수 없습니다.")
