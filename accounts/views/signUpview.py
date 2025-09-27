from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.serializers.signUpSerializer import SignUpSerializer

class SignUpView(APIView):
    # 인증 없이 접근 가능 (SessionAuthentication의 CSRF 검사 회피)
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = SignUpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                "id": user.id,
                "email": user.email,
                "created_at": user.created_at.isoformat(),
            },
            status=status.HTTP_201_CREATED,
        )