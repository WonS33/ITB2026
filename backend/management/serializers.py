from rest_framework import serializers

# 금액 최대 15자리 (999조 원 미만, 화면 입력칸과 같은 제한)
MAX_AMOUNT = 10**15 - 1

VALUE_FIELDS = (
    "product_sales",
    "merchandise_sales",
    "service_sales",
    "merchandise_purchase",
    "material_purchase",
    "expense",
)


def amount_field(**kwargs):
    return serializers.IntegerField(
        min_value=0,
        max_value=MAX_AMOUNT,
        error_messages={
            "min_value": "금액은 0원 이상이어야 합니다.",
            "max_value": "금액은 15자리까지 입력할 수 있습니다.",
            "invalid": "금액은 숫자만 입력할 수 있습니다.",
        },
        **kwargs,
    )


class MonthlyValuesSerializer(serializers.Serializer):
    product_sales = amount_field()
    merchandise_sales = amount_field()
    service_sales = amount_field()
    merchandise_purchase = amount_field()
    material_purchase = amount_field()
    expense = amount_field()


class OtherExpenseInputSerializer(serializers.Serializer):
    category_id = serializers.IntegerField()
    amount = amount_field()


class MonthlySaveSerializer(serializers.Serializer):
    """월간 입력 저장 요청 (화면 값은 믿지 않고 서버에서 다시 검사)"""

    # draft: 임시저장 / confirm: 확정 / update_confirmed: 확정된 달 수정(확정 유지)
    intent = serializers.ChoiceField(choices=["draft", "confirm", "update_confirmed"])
    values = MonthlyValuesSerializer()
    other_expenses = OtherExpenseInputSerializer(many=True, required=False, default=list)
    cash_balance = amount_field(required=False, allow_null=True, default=None)
    # 동시 수정 확인: 화면을 불러올 때 받은 updated_at 그대로 (처음 입력하는 달은 null)
    expected_updated_at = serializers.DateTimeField(allow_null=True)


class UnconfirmSerializer(serializers.Serializer):
    expected_updated_at = serializers.DateTimeField()


class TargetSaveSerializer(serializers.Serializer):
    """연간 목표 저장: 연간 목표매출액(필수, 0원 초과) + 분기 목표 4개(빈칸 = 자동 배분) + 직원 수(선택)"""

    target_amount = amount_field()
    quarters = serializers.ListField(child=amount_field(allow_null=True), min_length=4, max_length=4)
    headcount = serializers.IntegerField(
        min_value=1, max_value=9999, allow_null=True, required=False, default=None,
        error_messages={"min_value": "직원 수는 1명 이상입니다.", "max_value": "직원 수는 4자리까지 입력할 수 있습니다."},
    )
    expected_updated_at = serializers.DateTimeField(allow_null=True)

    def validate_target_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("연간 목표매출액을 입력하세요.")
        return value


NAME_MAX = 30


class CategoryItemSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True)  # null = 새 항목
    name = serializers.CharField(allow_blank=True, trim_whitespace=True)
    cost_type = serializers.ChoiceField(choices=["fixed", "variable", ""], allow_blank=True)
    is_active = serializers.BooleanField()

    def validate_name(self, value):
        value = " ".join(value.split())  # 앞뒤 공백 제거, 연속 공백 하나로
        if not value:
            raise serializers.ValidationError("항목 이름을 입력하세요.")
        if len(value) > NAME_MAX:
            raise serializers.ValidationError(f"항목 이름은 {NAME_MAX}자까지 입력할 수 있습니다.")
        return value


class CategoriesSaveSerializer(serializers.Serializer):
    """그 외 지출 항목 저장: 화면 순서대로 전체 목록 + 지울 항목 id + 불러올 때의 version(동시 수정 확인)"""

    items = CategoryItemSerializer(many=True, max_length=100)
    deleted_ids = serializers.ListField(child=serializers.IntegerField(), max_length=100, default=list)
    version = serializers.CharField()

    def validate_items(self, items):
        seen = set()
        for item in items:
            key = item["name"].lower()
            if key in seen:
                raise serializers.ValidationError(f'같은 이름의 항목이 있습니다: "{item["name"]}"')
            seen.add(key)
        return items
