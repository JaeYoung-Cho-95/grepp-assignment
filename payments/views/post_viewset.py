from django.db import transaction
from rest_framework.exceptions import APIException
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import GenericViewSet
from django.http import Http404
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND, HTTP_409_CONFLICT

from payments.models import Payment
from courses.models import CourseRegistration
from tests.models import TestRegistration


class PaymentViewSet(GenericViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Payment.objects.all()

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk):
        with transaction.atomic():
            payment = self._lock_payment_or_404(pk)
            registration = self._lock_registration_or_400(payment)
            self._ensure_ownership_with_registration_or_403(registration, request.user)
            self._validate_not_completed_or_409(registration)
            self._cancel_registration_if_needed(registration)
            self._cancel_payment_if_needed(payment)

        return Response(
            {
                "detail": "결제가 취소되었습니다.",
                "registration_id": registration.id,
                "payment_id": payment.id,
                "status": "cancelled",
            },
            status=HTTP_200_OK,
        )
        
    def _lock_payment_or_404(self, pk) -> Payment:
        try:
            return (
                Payment.objects
                .select_for_update()
                .only('id', 'course_registration_id', 'test_registration_id', 'status')
                .get(pk=pk)
            )
        except Payment.DoesNotExist:
            exc = APIException(detail="존재하지 않는 결제입니다.")
            exc.status_code = HTTP_404_NOT_FOUND
            raise exc

    def _lock_registration_or_400(self, payment: Payment):
        if payment.course_registration_id:
            return CourseRegistration.objects.select_for_update().get(pk=payment.course_registration_id)
        if payment.test_registration_id:
            return TestRegistration.objects.select_for_update().get(pk=payment.test_registration_id)
        exc = APIException(detail="연결된 신청 내역이 없습니다.")
        exc.status_code = HTTP_400_BAD_REQUEST
        raise exc

    def _cancel_registration_if_needed(self, registration) -> None:
        if getattr(registration, "status", "registered") != "cancelled":
            registration.status = "cancelled"
            registration.save(update_fields=["status"]) 

    def _cancel_payment_if_needed(self, payment: Payment) -> None:
        if payment.status != "cancelled":
            payment.status = "cancelled"
        payment.save(update_fields=["status"]) 

    def _ensure_ownership_with_registration_or_403(self, registration, user) -> None:
        user_id = getattr(registration, 'user_id', None)
        if user_id != user.id:
            from rest_framework.exceptions import APIException
            exc = APIException(detail="본인의 결제만 취소할 수 있습니다.")
            exc.status_code = HTTP_403_FORBIDDEN
            raise exc

    def _get_payment_or_404(self) -> Payment:
        try:
            return self.get_object()
        except Http404:
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
            exc = APIException(detail="본인의 결제만 취소할 수 있습니다.")
            exc.status_code = HTTP_403_FORBIDDEN
            raise exc

    def _get_registration_or_400(self, payment: Payment):
        registration = payment.course_registration or payment.test_registration
        if registration is None:
            exc = APIException(detail="연결된 신청 내역이 없습니다.")
            exc.status_code = HTTP_400_BAD_REQUEST
            raise exc
        return registration

    def _validate_not_completed_or_409(self, registration) -> None:
        status_value = getattr(registration, "status", "registered")
        if status_value == "completed":
            exc = APIException(detail="완료된 내역은 취소할 수 없습니다.")
            exc.status_code = HTTP_409_CONFLICT
            raise exc
        if status_value == "cancelled":
            exc = APIException(detail="이미 취소된 내역입니다.")
            exc.status_code = HTTP_409_CONFLICT
            raise exc
        if status_value not in {"registered", "in_progress"}:
            exc = APIException(detail="취소할 수 있는 상태가 아닙니다.")
            exc.status_code = HTTP_409_CONFLICT
            raise exc