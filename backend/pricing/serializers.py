from datetime import date

from rest_framework import serializers


class SettingChangeSerializer(serializers.Serializer):
    """화면에서 바꾸는 제품 가격 기준값 — 적용일은 오늘 이전만 (예정 기준값은 지원하지 않음)"""

    effective_date = serializers.DateField()
    exchange_rate = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=1, max_value=100000)
    customs_factor = serializers.DecimalField(max_digits=6, decimal_places=3, min_value=1, max_value=10)
    sga_rate = serializers.DecimalField(max_digits=6, decimal_places=2, min_value=0, max_value=1000)
    margin = serializers.DecimalField(max_digits=5, decimal_places=3, min_value=0.01, max_value=1)
    special_discount_rate = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100)
    commission_rate = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100)
    note = serializers.CharField(max_length=200, allow_blank=True, required=False)

    def validate_effective_date(self, value):
        if value > date.today():
            raise serializers.ValidationError("적용일은 오늘이나 그 이전 날짜여야 합니다.")
        return value
