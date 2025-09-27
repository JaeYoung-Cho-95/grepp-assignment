from rest_framework import serializers
from tests.models import Test

class TestListSerializer(serializers.ModelSerializer):
    is_registered = serializers.BooleanField(read_only=True)

    class Meta:
        model = Test
        fields = ('id', 'title', 'registrations_count', 'start_at', 'end_at', 'is_registered')