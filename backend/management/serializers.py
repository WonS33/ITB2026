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
