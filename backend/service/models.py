from django.db import models

from common.models import TimeStampedModel


class TripReport(TimeStampedModel):
    """출장보고서 (보고서 1건 = 출장 1회) — specs/06-service.md, specs/07-data-model.md 4절"""

    start_date = models.DateField("출장 시작일")  # 월 집계 기준
    end_date = models.DateField("출장 종료일", null=True, blank=True)
    extra_trip = models.CharField("추가 출장", max_length=50, blank=True)
    paid_type = models.CharField("비용청구 유무", max_length=10)  # 유상 / 무상
    requester_type = models.CharField("요청처 구분", max_length=30, blank=True)  # 예: 검색 불가
    requester = models.CharField("요청처", max_length=100)
    region = models.CharField("시·도", max_length=20)
    district = models.CharField("시·군", max_length=20, blank=True)  # 도 지역만. 특별·광역시는 빈 값
    work_type = models.CharField("작업 구분", max_length=30, blank=True)  # 예: 수리
    purpose = models.CharField("출장 목적", max_length=200, blank=True)
    fault_description = models.TextField("고장 내용", blank=True)  # 자유 서술 → 처음에는 저장·조회만
    work_description = models.TextField("작업 내용", blank=True)
    work_result = models.TextField("작업 결과", blank=True)
    author = models.CharField("작성자", max_length=50)

    class InputMethod(models.TextChoices):
        PDF = "pdf", "PDF 업로드"
        MANUAL = "manual", "직접 입력"

    # 데이터 출처 구분 (2026-10-21 추가. 그 전에 저장된 보고서는 모두 PDF 업로드)
    input_method = models.CharField("입력 방식", max_length=10, choices=InputMethod.choices, default=InputMethod.PDF)

    class Meta:
        verbose_name = "출장보고서"
        verbose_name_plural = verbose_name
        ordering = ["-start_date", "-id"]

    def __str__(self):
        return f"{self.start_date} {self.requester} ({self.author})"


class TripReportCompanion(models.Model):
    report = models.ForeignKey(TripReport, on_delete=models.CASCADE, related_name="companions")
    name = models.CharField("동행자", max_length=50)

    class Meta:
        verbose_name = "출장 동행자"
        verbose_name_plural = verbose_name


class TripReportProduct(models.Model):
    """제품 목록 (보고서 1건에 여러 개). 사양·일련번호는 제품마다 다르므로 여기에 둔다."""

    report = models.ForeignKey(TripReport, on_delete=models.CASCADE, related_name="products")
    model_name = models.CharField("모델명", max_length=50)  # 예: AVA03
    spec = models.CharField("사양", max_length=100, blank=True)
    serial_no_raw = models.CharField("일련번호(원문)", max_length=50, blank=True)  # 제조내역과 연결하지 않음
    quantity = models.PositiveIntegerField("수량", default=1)

    class Meta:
        verbose_name = "출장 제품"
        verbose_name_plural = verbose_name


class TripReportPart(models.Model):
    report = models.ForeignKey(TripReport, on_delete=models.CASCADE, related_name="parts")
    part_name = models.CharField("부품명", max_length=100)
    quantity = models.PositiveIntegerField("수량", null=True, blank=True)  # 보고서에 수량이 없으면 빈 값

    class Meta:
        verbose_name = "교체 부품"
        verbose_name_plural = verbose_name


class RequesterRegion(models.Model):
    """요청처 → 시·도·시·군 대응표. 업로드 확인 화면에서 고른 값을 저장해 다음부터 자동으로 채운다."""

    requester = models.CharField("요청처", max_length=100, unique=True)
    region = models.CharField("시·도", max_length=20)
    district = models.CharField("시·군", max_length=20, blank=True)

    class Meta:
        verbose_name = "요청처 지역"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.requester} → {self.region} {self.district}".strip()


class PartPrice(TimeStampedModel):
    """교체 부품 단가 (웹 직접 입력 또는 유상 A/S 견적서 PDF 업로드)

    단가가 바뀌면 덮어쓰지 않고 새 적용 시작일로 한 줄을 더한다 → 기간별 변동을 볼 수 있다.
    부품명은 출장보고서에 실제로 나온 이름(TripReportPart.part_name)과 같아야 연결된다.
    """

    class Source(models.TextChoices):
        MANUAL = "manual", "직접 입력"
        QUOTE = "quote", "견적서"

    part_name = models.CharField("부품명", max_length=100)
    unit_price = models.PositiveIntegerField("단가(원)")  # 부가세 제외
    effective_date = models.DateField("적용 시작일")
    # 출처 (2026-10-26 추가): 견적서 업로드로 넣은 단가는 견적 번호와 견적서의 품명 원문을 남긴다
    source = models.CharField("출처", max_length=10, choices=Source.choices, default=Source.MANUAL)
    quote_no = models.CharField("견적 번호", max_length=50, blank=True)
    quote_item = models.CharField("견적서 품명", max_length=200, blank=True)
    # 견적 단가는 출장 거리·작업 강도 등에 따라 달라질 수 있어, 이유를 참고할 수 있게 함께 남긴다 (2026-10-26)
    quote_company = models.CharField("견적 업체명", max_length=100, blank=True)  # 방문한 회사 (견적서 '업체명')
    quote_project = models.CharField("견적 사업명", max_length=200, blank=True)
    quote_note = models.TextField("견적 비고", blank=True)

    class Meta:
        verbose_name = "부품 단가"
        verbose_name_plural = verbose_name
        ordering = ["part_name", "effective_date"]
        constraints = [
            models.UniqueConstraint(fields=["part_name", "effective_date"], name="unique_part_price_per_date"),
        ]

    def __str__(self):
        return f"{self.part_name} {self.unit_price:,}원 ({self.effective_date}~)"


class QuotePartAlias(models.Model):
    """견적서 품명 → 부품명 대응표. 견적서 업로드 확인 화면에서 고른 부품명을 기억해 다음부터 자동으로 채운다.
    예: 견적서 "XX-01 가상 모터 Assy" → 출장보고서 부품명 "Motor" (요청처 → 지역 대응표와 같은 방식)"""

    quote_item = models.CharField("견적서 품명", max_length=200, unique=True)
    part_name = models.CharField("부품명", max_length=100)

    class Meta:
        verbose_name = "견적서 품명 대응"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.quote_item} → {self.part_name}"
