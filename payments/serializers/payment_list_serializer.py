from rest_framework import serializers
from payments.models import Payment

class PaymentListSerializer(serializers.ModelSerializer):
    target = serializers.SerializerMethodField()
    item_title = serializers.SerializerMethodField()
    attempted_at = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = (
            'amount',
            'payment_method',
            'target',
            'item_title',
            'status',
            'attempted_at',
        )

    def get_target(self, obj: Payment):
        return 'course' if obj.course_registration_id else 'test'

    def get_item_title(self, obj: Payment):
        if obj.course_registration_id and obj.course_registration and obj.course_registration.course:
            return obj.course_registration.course.title
        if obj.test_registration_id and obj.test_registration and obj.test_registration.test:
            return obj.test_registration.test.title
        return None

    def get_attempted_at(self, obj: Payment):
        if obj.course_registration_id and obj.course_registration:
            return obj.course_registration.attempted_at
        if obj.test_registration_id and obj.test_registration:
            return obj.test_registration.attempted_at
        return None