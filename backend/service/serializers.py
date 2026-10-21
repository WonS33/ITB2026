from rest_framework import serializers

from .models import PartPrice


class PartPriceSerializer(serializers.ModelSerializer):
    """단가 한 줄 입력: 부품명, 단가(원 단위 정수), 적용 시작일(YYYY-MM-DD)"""

    class Meta:
        model = PartPrice
        fields = ["id", "part_name", "unit_price", "effective_date"]
        validators = []  # 같은 날짜 중복은 아래 validate에서 한국어 메시지로 검사

    def validate_part_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("부품명을 골라 주세요.")
        return value

    def validate(self, data):
        if PartPrice.objects.filter(part_name=data["part_name"], effective_date=data["effective_date"]).exists():
            raise serializers.ValidationError(
                {"effective_date": "이 부품은 같은 적용 시작일의 단가가 이미 있습니다. 기존 줄을 지운 뒤 다시 입력해 주세요."}
            )
        return data
