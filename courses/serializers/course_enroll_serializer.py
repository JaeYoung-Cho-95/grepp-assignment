from rest_framework import serializers
from payments.models import Payment


class CourseEnrollSerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=1)
    payment_method = serializers.ChoiceField(choices=[m[0] for m in Payment.PAYMENT_METHOD_CHOICES])

    def validate(self, attrs):
        allowed_methods = {m[0] for m in Payment.PAYMENT_METHOD_CHOICES}
        method = str(attrs.get('payment_method', '')).strip().lower()
        if method not in allowed_methods:
            raise serializers.ValidationError({'payment_method': '지원하지 않는 결제수단입니다.'})
        attrs['payment_method'] = method

        amount = attrs.get('amount')
        if amount is None or amount <= 0:
            raise serializers.ValidationError({'amount': '금액은 1원 이상이어야 합니다.'})

        return attrs


