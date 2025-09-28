from django.db.models import Exists, OuterRef
from rest_framework.mixins import ListModelMixin
from rest_framework.viewsets import GenericViewSet
from rest_framework.permissions import IsAuthenticated
from tests.models import Test, TestRegistration
from tests.serializers.test_list_serializer import TestListSerializer
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_201_CREATED, HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND, HTTP_409_CONFLICT
from django.db import transaction, IntegrityError
from tests.serializers.test_apply_serializer import TestApplySerializer
from payments.models import Payment
from assignment.config.pagination_config import CustomPagination


class TestViewSet(ListModelMixin, GenericViewSet):
    serializer_class = TestListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get_queryset(self):
        user = self.request.user
        queryset = self._base_queryset_with_registration_flag(user)
        queryset = self._apply_status_filter(queryset)
        queryset = self._apply_sorting(queryset)
        return queryset

    @action(detail=True, methods=['post'], url_path='apply')
    def apply(self, request, pk=None):
        serializer = TestApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        test = self._get_test_or_404(pk)
        self._validate_test_is_applicable(test)
        self._ensure_not_already_applied(request.user, test)
        registration, payment = self._perform_apply_transaction(request.user, test, serializer.validated_data)
        return Response(
            data={
                'registration_id': registration.id,
                'payment_id': payment.id,
                'status': 'paid',
            },
            status=HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='complete')
    def complete(self, request, pk=None):
        test = self._get_test_or_404(pk)
        self._validate_test_is_completable(test)
        registration = self._get_registration_or_404(request.user, test)
        self._validate_registration_can_complete(registration)
        self._mark_registration_completed(registration)

        return Response({'registration_id': registration.id, 'status': 'completed'}, status=HTTP_200_OK)

    def _base_queryset_with_registration_flag(self, user):
        return Test.objects.all().annotate(
            is_registered=Exists(
                TestRegistration.objects.filter(user=user, test_id=OuterRef('pk'))
            ),
        )

    def _apply_status_filter(self, queryset):
        status_param = self.request.query_params.get('status')
        if status_param == 'available':
            now = timezone.now()
            return queryset.filter(is_active=True, is_registered=False, start_at__lte=now, end_at__gte=now)
        return queryset

    def _apply_sorting(self, queryset):
        sort = self.request.query_params.get('sort', 'created')
        if sort == 'popular':
            return queryset.order_by('-registrations_count', '-created_at')
        return queryset.order_by('-created_at')

    def _get_test_or_404(self, pk):
        try:
            return Test.objects.get(pk=pk)
        except Test.DoesNotExist:
            raise self._error(HTTP_404_NOT_FOUND, '존재하지 않는 시험입니다.')

    def _validate_test_is_applicable(self, test):
        now = timezone.now()
        if not (test.is_active and test.start_at <= now <= test.end_at):
            raise self._error(HTTP_400_BAD_REQUEST, '응시 가능한 시험이 아닙니다.')

    def _ensure_not_already_applied(self, user, test):
        if TestRegistration.objects.filter(user=user, test=test).exists():
            raise self._error(HTTP_409_CONFLICT, '이미 응시 신청된 시험입니다.')

    def _create_registration(self, user, test):
        return TestRegistration.objects.create(user=user, test=test)

    def _create_payment(self, test_registration, data):
        return Payment.objects.create(
            test_registration=test_registration,
            amount=data['amount'],
            payment_method=data['payment_method'],
            status='paid',
        )

    def _perform_apply_transaction(self, user, test, validated_data):
        with transaction.atomic():
            try:
                registration = self._create_registration(user, test)
            except IntegrityError:
                raise self._error(HTTP_409_CONFLICT, '이미 응시 신청된 시험입니다.')
            try:
                payment = self._create_payment(registration, validated_data)
            except IntegrityError:
                raise self._error(HTTP_409_CONFLICT, '결제 정보가 이미 생성되었습니다.')
        return registration, payment

    def _validate_test_is_completable(self, test):
        now = timezone.now()
        if not (test.is_active and test.start_at <= now <= test.end_at):
            raise self._error(HTTP_400_BAD_REQUEST, '응시 완료 가능한 시험이 아닙니다.')

    def _get_registration_or_404(self, user, test):
        try:
            return TestRegistration.objects.get(user=user, test=test)
        except TestRegistration.DoesNotExist:
            raise self._error(HTTP_404_NOT_FOUND, '응시 신청 이력이 없습니다.')

    def _validate_registration_can_complete(self, registration):
        if registration.status == 'completed':
            raise self._error(HTTP_409_CONFLICT, '이미 완료된 시험입니다.')
        if registration.status == 'cancelled':
            raise self._error(HTTP_400_BAD_REQUEST, '취소된 신청은 완료할 수 없습니다.')

    def _mark_registration_completed(self, registration):
        now = timezone.now()
        registration.status = 'completed'
        if registration.attempted_at is None:
            registration.attempted_at = now
        registration.save(update_fields=['status', 'attempted_at'])

    def _error(self, status_code, message):
        from rest_framework.exceptions import APIException
        exc = APIException(detail=message)
        exc.status_code = status_code
        return exc