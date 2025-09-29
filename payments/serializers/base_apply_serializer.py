from rest_framework import serializers
from payments.models import Payment


class BaseApplySerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=1)
    payment_method = serializers.ChoiceField(choices=[m[0] for m in Payment.PAYMENT_METHOD_CHOICES])

    def validate_payment_method(self, value):
        normalized = str(value).strip().lower()
        allowed_methods = {m[0] for m in Payment.PAYMENT_METHOD_CHOICES}
        if normalized not in allowed_methods:
            raise serializers.ValidationError('지원하지 않는 결제수단입니다.')
        return normalized

    def validate_amount(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError('금액은 1원 이상이어야 합니다.')
        return value


