from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework.serializers import ModelSerializer, EmailField, CharField
from rest_framework.validators import UniqueValidator

User = get_user_model()

class SignUpSerializer(ModelSerializer):
    email = EmailField(
        validators=[UniqueValidator(queryset=User.objects.all(), message="이미 사용 중인 이메일입니다.")]
    )
    password = CharField(write_only=True, trim_whitespace=False)

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        return User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
        )

    class Meta:
        model = User
        fields = ("id", "email", "password", "created_at")
        read_only_fields = ("id", "created_at")