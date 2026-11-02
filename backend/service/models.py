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


class PriceStandard(models.Model):
    """뉴토크 기준값 전체 기본값 (한 줄만 씀, id=1)

    뉴토크 기준값 = 단가표 기준단가 × (1 − 할인율 ÷ 100) + 추가단가 (원 단위 반올림)
    부품마다 따로 정하지 않으면 이 기본값을 쓴다 (specs/09-metrics.md 4절)
    """

    default_discount_rate = models.DecimalField("기본 할인율(%)", max_digits=5, decimal_places=2, default=0)
    default_extra_price = models.IntegerField("기본 추가단가(원)", default=0)
    updated_at = models.DateTimeField("수정 일시", auto_now=True)

    class Meta:
        verbose_name = "뉴토크 기준값 기본 설정"
        verbose_name_plural = verbose_name

    @classmethod
    def get(cls):
        return cls.objects.get_or_create(pk=1)[0]


class PartCatalogItem(TimeStampedModel):
    """부품 단가표 1줄 (파트넘버별 기준단가) — 기업 단가표 파일을 import_part_catalog 명령으로 넣는다

    실제 단가표는 대외비라 Git·배포 서버에 올리지 않고 로컬 DB에만 넣는다 (CLAUDE.md 7절).
    같은 파트넘버가 두 품목에 쓰인 경우가 있어(원본 확인 필요) 파트넘버 + 품명을 기준으로 구분한다.
    """

    part_no = models.CharField("파트넘버", max_length=30, db_index=True)  # 예: XX-05-A-01
    category = models.CharField("분류", max_length=50, blank=True)  # 예: 05 MOTOR
    name = models.CharField("품명", max_length=100)
    applies_to = models.CharField("적용 모델(적요)", max_length=100, blank=True)  # 예: NTI-01 ~ 03
    list_price = models.PositiveIntegerField("단가표 기준단가(원)", null=True, blank=True)  # "-"이면 비움
    # 단가표 기준일: 원본에 날짜가 없어 가져올 때 정한다 (2026-11-02 사용자 결정: 임시로 2026-11-01)
    list_price_date = models.DateField("단가표 기준일", null=True, blank=True)
    # 부품마다 따로 정할 때만 채운다. 비어 있으면 PriceStandard 기본값을 쓴다
    discount_rate = models.DecimalField("할인율(%)", max_digits=5, decimal_places=2, null=True, blank=True)
    extra_price = models.IntegerField("추가단가(원)", null=True, blank=True)
    sort_order = models.PositiveIntegerField("단가표 순서", default=0)

    class Meta:
        verbose_name = "부품 단가표"
        verbose_name_plural = verbose_name
        ordering = ["sort_order", "part_no"]
        constraints = [models.UniqueConstraint(fields=["part_no", "name"], name="unique_catalog_part_no_name")]

    def __str__(self):
        return f"{self.part_no} {self.name}"


class PartPrice(TimeStampedModel):
    """교체 부품 단가 (웹 직접 입력 또는 유상 A/S 견적서 PDF 업로드)

    단가가 바뀌면 덮어쓰지 않고 새 적용 시작일로 한 줄을 더한다 → 기간별 변동을 볼 수 있다.
    부품명은 출장보고서에 실제로 나온 이름(TripReportPart.part_name)과 같아야 연결된다.
    """

    class Source(models.TextChoices):
        MANUAL = "manual", "직접 입력"
        QUOTE = "quote", "견적서"

    part_name = models.CharField("부품명", max_length=100)
    # 단가표 파트넘버와 연결 (2026-11-02): 출장지(업체)별 단가를 뉴토크 기준값과 비교한다
    catalog_item = models.ForeignKey(
        PartCatalogItem, verbose_name="단가표 부품", null=True, blank=True, on_delete=models.SET_NULL, related_name="prices"
    )
    unit_price = models.PositiveIntegerField("단가(원)")  # 부가세 제외
    effective_date = models.DateField("적용 시작일")
    # 출처 (2026-10-26 추가): 견적서 업로드로 넣은 단가는 견적 번호와 견적서의 품명 원문을 남긴다
    source = models.CharField("출처", max_length=10, choices=Source.choices, default=Source.MANUAL)
    quote_no = models.CharField("견적 번호", max_length=50, blank=True)
    quote_item = models.CharField("견적서 품명", max_length=200, blank=True)
    # 견적 단가는 출장 거리·작업 강도 등에 따라 달라질 수 있어, 이유를 참고할 수 있게 함께 남긴다 (2026-10-26)
    quote_company = models.CharField("업체명(출장지)", max_length=100, blank=True)  # 방문한 회사 (견적서 '업체명')
    quote_project = models.CharField("견적 사업명", max_length=200, blank=True)
    quote_note = models.TextField("견적 비고", blank=True)

    class Meta:
        verbose_name = "부품 단가"
        verbose_name_plural = verbose_name
        ordering = ["part_name", "effective_date"]
        # 같은 부품이라도 업체(출장지)마다 단가가 다를 수 있다 → 부품 + 업체 + 날짜로 한 줄
        constraints = [
            models.UniqueConstraint(
                fields=["catalog_item", "quote_company", "effective_date"],
                condition=models.Q(catalog_item__isnull=False),
                name="unique_catalog_price_per_company_date",
            ),
            models.UniqueConstraint(
                fields=["part_name", "quote_company", "effective_date"],
                condition=models.Q(catalog_item__isnull=True),
                name="unique_part_price_per_company_date",
            ),
        ]

    def __str__(self):
        return f"{self.part_name} {self.unit_price:,}원 ({self.effective_date}~)"


class QuotePartAlias(models.Model):
    """견적서 품명 → 부품명 대응표. 견적서 업로드 확인 화면에서 고른 부품명을 기억해 다음부터 자동으로 채운다.
    예: 견적서 "XX-01 가상 모터 Assy" → 출장보고서 부품명 "Motor" (요청처 → 지역 대응표와 같은 방식)"""

    quote_item = models.CharField("견적서 품명", max_length=200, unique=True)
    part_name = models.CharField("부품명", max_length=100)
    catalog_item = models.ForeignKey(PartCatalogItem, verbose_name="단가표 부품", null=True, blank=True,
                                     on_delete=models.SET_NULL)

    class Meta:
        verbose_name = "견적서 품명 대응"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.quote_item} → {self.part_name}"
