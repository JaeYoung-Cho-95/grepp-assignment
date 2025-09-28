from django.db import transaction
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import GenericViewSet
from django.http import Http404
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND, HTTP_409_CONFLICT

from payments.models import Payment


class PaymentViewSet(GenericViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Payment.objects.all()

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk):
        payment = self._get_payment_or_404()
        self._ensure_ownership_or_403(payment, request.user)
        registration = self._get_registration_or_400(payment)
        self._validate_not_completed_or_409(registration)

        with transaction.atomic():
            if getattr(registration, "status", "registered") != "cancelled":
                registration.status = "cancelled"
                registration.save(update_fields=["status"]) 

            if payment.status != "cancelled":
                payment.status = "cancelled"
            payment.save(update_fields=["status"]) 

        return Response(
            {
                "detail": "결제가 취소되었습니다.",
                "registration_id": registration.id,
                "payment_id": payment.id,
                "status": "cancelled",
            },
            status=HTTP_200_OK,
        )
        
    def _get_payment_or_404(self) -> Payment:
        try:
            return self.get_object()
        except Http404:
            from rest_framework.exceptions import APIException
            exc = APIException(detail="존재하지 않는 결제입니다.")
            exc.status_code = HTTP_404_NOT_FOUND
            raise exc

    def _ensure_ownership_or_403(self, payment: Payment, user) -> None:
        if payment.course_registration_id:
            ok = payment.course_registration.user_id == user.id
        elif payment.test_registration_id:
            ok = payment.test_registration.user_id == user.id
        else:
            ok = False
        if not ok:
            from rest_framework.exceptions import APIException
            exc = APIException(detail="본인의 결제만 취소할 수 있습니다.")
            exc.status_code = HTTP_403_FORBIDDEN
            raise exc

    def _get_registration_or_400(self, payment: Payment):
        registration = payment.course_registration or payment.test_registration
        if registration is None:
            from rest_framework.exceptions import APIException
            exc = APIException(detail="연결된 신청 내역이 없습니다.")
            exc.status_code = HTTP_400_BAD_REQUEST
            raise exc
        return registration

    def _validate_not_completed_or_409(self, registration) -> None:
        if getattr(registration, "status", "registered") == "completed":
            from rest_framework.exceptions import APIException
            exc = APIException(detail="완료된 내역은 취소할 수 없습니다.")
            exc.status_code = HTTP_409_CONFLICT
            raise exc