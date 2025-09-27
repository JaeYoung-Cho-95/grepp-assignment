from datetime import date, datetime, time as dtime
from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins, permissions, viewsets
from rest_framework.exceptions import ValidationError

from payments.models import Payment
from payments.serializers.payment_list_serializer import PaymentListSerializer

class MePaymentsViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PaymentListSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Payment.objects.select_related(
            'course_registration__course',
            'test_registration__test',
        ).filter(
            Q(course_registration__user=user) | Q(test_registration__user=user)
        ).order_by('-created_at')

        status_param = self.request.query_params.get('status')
        if status_param:
            allowed = {'paid', 'cancelled'}
            if status_param not in allowed:
                raise ValidationError({'status': f'허용값: {", ".join(sorted(allowed))}'})
            qs = qs.filter(status=status_param)

        from_str = self.request.query_params.get('from')
        to_str = self.request.query_params.get('to')
        if from_str or to_str:
            try:
                dt_from = None
                dt_to = None
                if from_str:
                    d_from = date.fromisoformat(from_str)
                    dt_from = timezone.make_aware(datetime.combine(d_from, dtime.min))
                if to_str:
                    d_to = date.fromisoformat(to_str)
                    dt_to = timezone.make_aware(datetime.combine(d_to, dtime.max))
            except Exception:
                raise ValidationError({'from/to': 'YYYY-MM-DD 형식이어야 합니다.'})

            if status_param == 'paid':
                if dt_from:
                    qs = qs.filter(paid_at__gte=dt_from)
                if dt_to:
                    qs = qs.filter(paid_at__lte=dt_to)
            elif status_param == 'cancelled':
                if dt_from:
                    qs = qs.filter(canceled_at__gte=dt_from)
                if dt_to:
                    qs = qs.filter(canceled_at__lte=dt_to)
            else:
                if dt_from:
                    qs = qs.filter(created_at__gte=dt_from)
                if dt_to:
                    qs = qs.filter(created_at__lte=dt_to)

        return qs