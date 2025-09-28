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
from assignment.common.api_errors import api_error


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
            raise api_error(HTTP_404_NOT_FOUND, "존재하지 않는 결제입니다.")

    def _lock_registration_or_400(self, payment: Payment):
        if payment.course_registration_id:
            return CourseRegistration.objects.select_for_update().get(pk=payment.course_registration_id)
        if payment.test_registration_id:
            return TestRegistration.objects.select_for_update().get(pk=payment.test_registration_id)
        raise api_error(HTTP_400_BAD_REQUEST, "연결된 신청 내역이 없습니다.")

    def _cancel_registration_if_needed(self, registration) -> None:
        if getattr(registration, "status", "registered") != "cancelled":
            registration.status = "cancelled"
            registration.save(update_fields=["status"]) 

    def _cancel_payment_if_needed(self, payment: Payment) -> None:
        if payment.status != "cancelled":
            payment.status = "cancelled"
        payment.save(update_fields=["status","canceled_at"]) 

    def _ensure_ownership_with_registration_or_403(self, registration, user) -> None:
        user_id = getattr(registration, 'user_id', None)
        if user_id != user.id:
            raise api_error(HTTP_403_FORBIDDEN, "본인의 결제만 취소할 수 있습니다.")

    def _get_payment_or_404(self) -> Payment:
        try:
            return self.get_object()
        except Http404:
            raise api_error(HTTP_404_NOT_FOUND, "존재하지 않는 결제입니다.")

    def _get_registration_or_400(self, payment: Payment):
        registration = payment.course_registration or payment.test_registration
        if registration is None:
            raise api_error(HTTP_400_BAD_REQUEST, "연결된 신청 내역이 없습니다.")
        return registration

    def _validate_not_completed_or_409(self, registration) -> None:
        status_value = getattr(registration, "status", "registered")
        if status_value == "completed":
            raise api_error(HTTP_409_CONFLICT, "완료된 내역은 취소할 수 없습니다.")
        if status_value == "cancelled":
            raise api_error(HTTP_409_CONFLICT, "이미 취소된 내역입니다.")
        if status_value not in {"registered", "in_progress"}:
            raise api_error(HTTP_409_CONFLICT, "취소할 수 있는 상태가 아닙니다.")