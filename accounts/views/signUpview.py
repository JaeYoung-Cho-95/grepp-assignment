from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.generics import CreateAPIView

from accounts.serializers.signUpSerializer import SignUpSerializer

class SignUpView(CreateAPIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    serializer_class = SignUpSerializer

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        response.status_code = status.HTTP_201_CREATED
        return response

    


