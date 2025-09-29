from rest_framework_simplejwt.views import TokenObtainPairView
from drf_spectacular.utils import extend_schema, OpenApiExample

@extend_schema(
    tags=['계정'],
    summary='로그인',
    examples=[
        OpenApiExample(
            '로그인 예시',
            value={'email': 'normal@example.com', 'password': 'normal1234'},
            request_only=True,
        ),
    ],
)
class CustomTokenObtainPairView(TokenObtainPairView):
    pass