from rest_framework import serializers
from courses.models import Course

class CourseListSerializer(serializers.ModelSerializer):
    is_registered = serializers.BooleanField(read_only=True)

    class Meta:
        model = Course
        fields = ('id', 'title', 'registrations_count', 'start_at', 'end_at', 'is_registered')