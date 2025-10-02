from django.utils import timezone
from django.db import transaction, IntegrityError
from rest_framework.mixins import ListModelMixin
from rest_framework.viewsets import GenericViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_201_CREATED

from assignment.config.pagination_config import CustomCursorPagination
from assignment.common.api_errors import api_error
from payments.serializers.base_apply_serializer import BaseApplySerializer


class BaseRegistrableViewSet(ListModelMixin, GenericViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = CustomCursorPagination
    apply_serializer_class = BaseApplySerializer

    def apply_status_and_sort(self, queryset):
        status_param = self.request.query_params.get('status')
        if status_param == 'available':
            queryset = queryset.filter(is_active=True, is_registered=False)

        sort = self.request.query_params.get('sort', 'created')
        if sort == 'popular':
            return queryset.order_by('-registrations_count', '-created_at')
        
        return queryset.order_by('-created_at')

    def do_apply(self, request, pk, *,
                 serializer_class,
                 get_item_or_404,
                 validate_item_is_applicable,
                 ensure_not_already_registered,
                 create_registration,
                 create_payment,
                 registration_conflict_message: str,
                 payment_conflict_message: str):
        serializer = serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        item = get_item_or_404(pk)
        validate_item_is_applicable(item)
        ensure_not_already_registered(request.user, item)

        with transaction.atomic():
            try:
                registration = create_registration(request.user, item)
            except IntegrityError:
                raise api_error(409, registration_conflict_message)
            try:
                payment = create_payment(registration, serializer.validated_data)
            except IntegrityError:
                raise api_error(409, payment_conflict_message)

        return Response(
            data={
                'registration_id': registration.id,
                'payment_id': payment.id,
                'status': 'paid',
            },
            status=HTTP_201_CREATED,
        )

    def do_complete(self, request, pk, *,
                    get_item_or_404,
                    validate_item_is_completable,
                    get_registration_or_404,
                    validate_registration_can_complete,
                    mark_registration_completed):
                    
        with transaction.atomic():
            item = get_item_or_404(pk)
            validate_item_is_completable(item)
            registration = get_registration_or_404(request.user, item)
            try:
                registration = registration.__class__.objects.select_for_update().get(pk=registration.pk)
            except Exception:
                pass
            validate_registration_can_complete(registration)
            mark_registration_completed(registration)

        return Response({'registration_id': registration.id, 'status': 'completed'}, status=HTTP_200_OK)
        
    def validate_registration_can_complete_default(self, registration):
        status_value = getattr(registration, 'status', 'registered')
        if status_value == 'completed':
            raise api_error(409, '이미 완료된 신청입니다.')
        if status_value == 'cancelled':
            raise api_error(400, '취소된 신청은 완료할 수 없습니다.')
        if status_value not in {'registered', 'in_progress'}:
            raise api_error(409, '완료할 수 있는 상태가 아닙니다.')

    def mark_registration_completed_default(self, registration):
        now = timezone.now()
        registration.status = 'completed'
        if getattr(registration, 'attempted_at', None) is None:
            registration.attempted_at = now
        registration.save(update_fields=['status', 'attempted_at'])


