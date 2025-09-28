from rest_framework.serializers import ModelSerializer, SerializerMethodField
from payments.models import Payment

class PaymentListSerializer(ModelSerializer):
    target = SerializerMethodField()
    item_title = SerializerMethodField()
    course_id = SerializerMethodField()
    test_id = SerializerMethodField()
    attempted_at = SerializerMethodField()

    class Meta:
        model = Payment
        fields = (
            'amount',
            'payment_method',
            'target',
            'course_id',
            'test_id',
            'item_title',
            'status',
            'attempted_at',
        )

    def get_target(self, obj: Payment):
        return 'course' if obj.course_registration_id else 'test'

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

    def get_course_id(self, obj: Payment):
        if obj.course_registration_id:
            return getattr(obj.course_registration, 'course_id', None)
        return None

    def get_test_id(self, obj: Payment):
        if obj.test_registration_id:
            return getattr(obj.test_registration, 'test_id', None)
        return None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        target = data.get('target')
        if target == 'course':
            data.pop('test_id', None)
        elif target == 'test':
            data.pop('course_id', None)
        return data