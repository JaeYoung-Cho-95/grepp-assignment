from django.db.models import Exists, OuterRef, Q
from rest_framework import mixins, permissions, viewsets
from courses.models import Course, CourseRegistration
from courses.serializers.course_list_serializer import CourseListSerializer
from django.utils import timezone

class CourseViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = CourseListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Course.objects.all().annotate(
            is_registered=Exists(
                CourseRegistration.objects.filter(user=user, course_id=OuterRef('pk'))
            ),
        )

        status_param = self.request.query_params.get('status')
        if status_param == 'available':
            now = timezone.now()
            qs = qs.filter(is_active=True, is_registered=False, start_at__lte=now, end_at__gte=now)

        q = self.request.query_params.get('q')
        if q:
            qs = qs.filter(Q(title__icontains=q))

        sort = self.request.query_params.get('sort', 'created')
        if sort == 'popular':
            return qs.order_by('-registrations_count', '-created_at')
        return qs.order_by('-created_at')