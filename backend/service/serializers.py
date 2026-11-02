from rest_framework import serializers

from .catalog import duplicate_price_exists
from .models import PartCatalogItem, PartPrice


class PartPriceSerializer(serializers.ModelSerializer):
    """단가 한 줄 입력: 단가표 부품(파트넘버), 업체(출장지), 단가(원 단위 정수), 적용 시작일(YYYY-MM-DD)

    부품명은 단가표 품명으로 채운다. 같은 부품·같은 업체·같은 날짜는 한 줄만 둔다.
    """

    catalog_item = serializers.PrimaryKeyRelatedField(
        queryset=PartCatalogItem.objects.all(), error_messages={"required": "파트넘버를 골라 주세요.",
                                                                 "null": "파트넘버를 골라 주세요.",
                                                                 "does_not_exist": "단가표에 없는 부품입니다."}
    )
    quote_company = serializers.CharField(max_length=100, error_messages={"blank": "업체(출장지)를 입력해 주세요.",
                                                                           "required": "업체(출장지)를 입력해 주세요."})

    class Meta:
        model = PartPrice
        fields = ["id", "catalog_item", "part_name", "quote_company", "unit_price", "effective_date", "quote_note"]
        read_only_fields = ["part_name"]
        extra_kwargs = {"quote_note": {"required": False}}
        validators = []  # 같은 날짜 중복은 아래 validate에서 한국어 메시지로 검사

    def validate_quote_company(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("업체(출장지)를 입력해 주세요.")
        return value

    def validate(self, data):
        if duplicate_price_exists(data["catalog_item"], data["quote_company"], data["effective_date"]):
            raise serializers.ValidationError(
                {"effective_date": "이 부품은 같은 업체·같은 적용 시작일의 단가가 이미 있습니다. 기존 줄을 지운 뒤 다시 입력해 주세요."}
            )
        data["part_name"] = data["catalog_item"].name
        return data


class CatalogSettingSerializer(serializers.Serializer):
    """뉴토크 기준값 설정: 할인율(%) 0~100, 추가단가(원). 부품별 설정에서 null이면 전체 기본값을 쓴다"""

    discount_rate = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100, allow_null=True)
    extra_price = serializers.IntegerField(allow_null=True, min_value=-100_000_000, max_value=100_000_000)
