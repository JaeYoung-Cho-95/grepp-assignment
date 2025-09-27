from rest_framework.serializers import ModelSerializer, BooleanField
from courses.models import Course

class CourseListSerializer(ModelSerializer):
    is_registered = BooleanField(read_only=True)

    class Meta:
        model = Course
        fields = ('id', 'title', 'registrations_count', 'start_at', 'end_at', 'is_registered')
        read_only_fields = ('id', 'registrations_count')