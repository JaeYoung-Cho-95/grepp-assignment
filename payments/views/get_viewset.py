from datetime import date, datetime, time as dtime
from django.db.models import Q
from django.utils.timezone import make_aware
from rest_framework.permissions import IsAuthenticated
from rest_framework.mixins import ListModelMixin
from rest_framework.viewsets import GenericViewSet
from rest_framework.exceptions import ValidationError

from payments.models import Payment
from payments.serializers.payment_list_serializer import PaymentListSerializer

class MePaymentsViewSet(ListModelMixin, GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = PaymentListSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = self._base_queryset(user)
        status_param = self.request.query_params.get('status')
        queryset = self._apply_status_filter(queryset, status_param)
        queryset = self._apply_date_range_filter(queryset, status_param)
        return queryset

    def _base_queryset(self, user):
        return Payment.objects.select_related(
            'course_registration__course',
            'test_registration__test',
        ).filter(
            Q(course_registration__user=user) | Q(test_registration__user=user)
        ).order_by('-created_at')

    def _apply_status_filter(self, queryset, status_param):
        if not status_param:
            return queryset
        allowed = {'paid', 'cancelled'}
        if status_param not in allowed:
            raise ValidationError({'status': f'허용값: {", ".join(sorted(allowed))}'})
        return queryset.filter(status=status_param)

    def _apply_date_range_filter(self, queryset, status_param):
        from_str = self.request.query_params.get('from')
        to_str = self.request.query_params.get('to')
        if not (from_str or to_str):
            return queryset
        dt_from, dt_to = self._parse_date_range_or_400(from_str, to_str)
        if status_param == 'paid':
            if dt_from:
                queryset = queryset.filter(paid_at__gte=dt_from)
            if dt_to:
                queryset = queryset.filter(paid_at__lte=dt_to)
        elif status_param == 'cancelled':
            if dt_from:
                queryset = queryset.filter(canceled_at__gte=dt_from)
            if dt_to:
                queryset = queryset.filter(canceled_at__lte=dt_to)
        else:
            if dt_from:
                queryset = queryset.filter(created_at__gte=dt_from)
            if dt_to:
                queryset = queryset.filter(created_at__lte=dt_to)
        return queryset

    def _parse_date_range_or_400(self, from_str, to_str):
        try:
            dt_from = None
            dt_to = None
            if from_str:
                d_from = date.fromisoformat(from_str)
                dt_from = make_aware(datetime.combine(d_from, dtime.min))
            if to_str:
                d_to = date.fromisoformat(to_str)
                dt_to = make_aware(datetime.combine(d_to, dtime.max))
            return dt_from, dt_to
        except Exception:
            raise ValidationError({'from/to': 'YYYY-MM-DD 형식이어야 합니다.'})