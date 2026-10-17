from rest_framework import serializers


class ProductionTargetInputSerializer(serializers.Serializer):
    target_quantity = serializers.IntegerField(min_value=0, max_value=1_000_000)
