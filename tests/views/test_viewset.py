from django.db.models import Exists, OuterRef
from tests.models import Test, TestRegistration
from tests.serializers.test_list_serializer import TestListSerializer
from django.utils import timezone
from rest_framework.decorators import action
from tests.serializers.test_apply_serializer import TestApplySerializer
from payments.models import Payment
from assignment.common.api_errors import api_error
from assignment.common.base_registrable_viewset import BaseRegistrableViewSet


class TestViewSet(BaseRegistrableViewSet):
    serializer_class = TestListSerializer
    apply_serializer_class = TestApplySerializer

    def get_queryset(self):
        user = self.request.user
        queryset = self._base_queryset_with_registration_flag(user)
        return self.apply_status_and_sort(queryset)

    @action(detail=True, methods=['post'], url_path='apply')
    def apply(self, request, pk=None):
        return self.do_apply(
            request,
            pk,
            serializer_class=self.apply_serializer_class,
            get_item_or_404=self._get_test_or_404,
            validate_item_is_applicable=self._validate_test_is_applicable,
            ensure_not_already_registered=self._ensure_not_already_applied,
            create_registration=self._create_registration,
            create_payment=self._create_payment,
            registration_conflict_message='이미 응시 신청된 시험입니다.',
            payment_conflict_message='결제 정보가 이미 생성되었습니다.',
        )

    @action(detail=True, methods=['post'], url_path='complete')
    def complete(self, request, pk=None):
        return self.do_complete(
            request,
            pk,
            get_item_or_404=self._get_test_or_404,
            validate_item_is_completable=self._validate_test_is_completable,
            get_registration_or_404=self._get_registration_or_404,
            validate_registration_can_complete=self.validate_registration_can_complete_default,
            mark_registration_completed=self.mark_registration_completed_default,
        )

    def _base_queryset_with_registration_flag(self, user):
        return Test.objects.all().annotate(
            is_registered=Exists(
                TestRegistration.objects.filter(user=user, test_id=OuterRef('pk'))
            ),
        )

    def _get_test_or_404(self, pk):
        try:
            return Test.objects.get(pk=pk)
        except Test.DoesNotExist:
            raise api_error(404, '존재하지 않는 시험입니다.')

    def _validate_test_is_applicable(self, test):
        now = timezone.now()
        if not (test.is_active and test.start_at <= now <= test.end_at):
            raise api_error(400, '응시 가능한 시험이 아닙니다.')

    def _ensure_not_already_applied(self, user, test):
        if TestRegistration.objects.filter(user=user, test=test).exists():
            raise api_error(409, '이미 응시 신청된 시험입니다.')

    def _create_registration(self, user, test):
        return TestRegistration.objects.create(user=user, test=test)

    def _create_payment(self, test_registration, data):
        return Payment.objects.create(
            test_registration=test_registration,
            amount=data['amount'],
            payment_method=data['payment_method'],
            status='paid',
        )

    def _validate_test_is_completable(self, test):
        now = timezone.now()
        if not (test.is_active and test.start_at <= now <= test.end_at):
            raise api_error(400, '응시 완료 가능한 시험이 아닙니다.')

    def _get_registration_or_404(self, user, test):
        try:
            return TestRegistration.objects.get(user=user, test=test)
        except TestRegistration.DoesNotExist:
            raise api_error(404, '응시 신청 이력이 없습니다.')