from django.db import transaction
from rest_framework import permissions, status, viewsets
from django.http import Http404
from rest_framework.decorators import action
from rest_framework.response import Response

from payments.models import Payment


class PaymentViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Payment.objects.all()

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk):
        try:
            payment = self.get_object()
        except Http404:
            return Response({"detail": "존재하지 않는 결제입니다."}, status=status.HTTP_404_NOT_FOUND)

        if not self._ensure_ownership(payment, request.user):
            return Response({"detail": "본인의 결제만 취소할 수 있습니다."}, status=status.HTTP_403_FORBIDDEN)

        registration = payment.course_registration or payment.test_registration
        if registration is None:
            return Response({"detail": "연결된 신청 내역이 없습니다."}, status=status.HTTP_400_BAD_REQUEST)

        if getattr(registration, "status", "registered") == "completed":
            return Response({"detail": "완료된 내역은 취소할 수 없습니다."}, status=status.HTTP_409_CONFLICT)

        with transaction.atomic():
            deleted_registration_id = registration.id
            registration.delete()

        return Response(
            {
                "detail": "결제가 취소되었습니다.",
                "deleted_registration_id": deleted_registration_id,
            },
            status=status.HTTP_200_OK,
        )
        
    def _ensure_ownership(self, payment: Payment, user) -> bool:
        if payment.course_registration_id:
            return payment.course_registration.user_id == user.id
        if payment.test_registration_id:
            return payment.test_registration.user_id == user.id
        return False