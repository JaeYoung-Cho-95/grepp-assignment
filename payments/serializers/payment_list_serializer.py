from rest_framework.serializers import ModelSerializer, SerializerMethodField
from payments.models import Payment

class PaymentListSerializer(ModelSerializer):
    item_title = SerializerMethodField()
    attempted_at = SerializerMethodField()
    can_refund = SerializerMethodField()

    class Meta:
        model = Payment
        fields = (
            'id',
            'amount',
            'payment_method',
            'item_title',
            'status',
            'can_refund',
            'attempted_at',
        )

    def get_item_title(self, obj: Payment):
        course_title = getattr(getattr(obj.course_registration, 'course', None), 'title', None) if obj.course_registration_id else None
        if course_title is not None:
            return course_title
        test_title = getattr(getattr(obj.test_registration, 'test', None), 'title', None) if obj.test_registration_id else None
        return test_title

    def get_attempted_at(self, obj: Payment):
        course_attempted = getattr(obj.course_registration, 'attempted_at', None) if obj.course_registration_id else None
        if course_attempted is not None:
            return course_attempted
        test_attempted = getattr(obj.test_registration, 'attempted_at', None) if obj.test_registration_id else None
        return test_attempted

    def get_can_refund(self, obj: Payment):
        registration = obj.course_registration if obj.course_registration_id else obj.test_registration if obj.test_registration_id else None
        if registration is None:
            return False
        status_value = getattr(registration, 'status', None)
        return status_value in {'registered', 'in_progress'}