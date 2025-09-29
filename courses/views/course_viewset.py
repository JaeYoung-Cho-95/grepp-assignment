from django.db.models import Exists, OuterRef
from courses.models import Course, CourseRegistration
from courses.serializers.course_list_serializer import CourseListSerializer
from django.utils import timezone
from rest_framework.decorators import action
from courses.serializers.course_enroll_serializer import CourseEnrollSerializer
from payments.models import Payment
from assignment.common.api_errors import api_error
from assignment.common.base_registrable_viewset import BaseRegistrableViewSet


class CourseViewSet(BaseRegistrableViewSet):
    serializer_class = CourseListSerializer
    apply_serializer_class = CourseEnrollSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = self._base_queryset_with_registration_flag(user)
        return self.apply_status_and_sort(queryset)

    @action(detail=True, methods=['post'], url_path='complete')
    def complete(self, request, pk=None):
        return self.do_complete(
            request,
            pk,
            get_item_or_404=self._get_course_or_404,
            validate_item_is_completable=self._validate_course_is_completable,
            get_registration_or_404=self._get_registration_or_404,
            validate_registration_can_complete=self.validate_registration_can_complete_default,
            mark_registration_completed=self.mark_registration_completed_default,
        )
    
    @action(detail=True, methods=['post'], url_path='enroll')
    def enroll(self, request, pk=None):
        return self.do_apply(
            request,
            pk,
            serializer_class=self.apply_serializer_class,
            get_item_or_404=self._get_course_or_404,
            validate_item_is_applicable=self._validate_course_is_enrollable,
            ensure_not_already_registered=self._ensure_not_already_registered,
            create_registration=self._create_registration,
            create_payment=self._create_payment,
            registration_conflict_message='이미 수업 수강 신청된 수업입니다.',
            payment_conflict_message='결제 정보가 이미 생성되었습니다.',
        )

    def _base_queryset_with_registration_flag(self, user):
        return Course.objects.all().annotate(
            is_registered=Exists(
                CourseRegistration.objects.filter(user=user, course_id=OuterRef('pk'))
            ),
        )

    def _get_course_or_404(self, pk):
        try:
            return Course.objects.get(pk=pk)
        except Course.DoesNotExist:
            raise api_error(404, '존재하지 않는 수업입니다.')

    def _validate_course_is_enrollable(self, course):
        now = timezone.now()
        if not (course.is_active and course.start_at <= now <= course.end_at):
            raise api_error(400, '수업 수강 가능한 수업이 아닙니다.')

    def _ensure_not_already_registered(self, user, course):
        if CourseRegistration.objects.filter(user=user, course=course).exists():
            raise api_error(409, '이미 수업 수강 신청된 수업입니다.')

    def _create_registration(self, user, course):
        return CourseRegistration.objects.create(user=user, course=course)

    def _create_payment(self, course_registration, data):
        return Payment.objects.create(
            course_registration=course_registration,
            amount=data['amount'],
            payment_method=data['payment_method'],
            status='paid',
        )

    def _validate_course_is_completable(self, course):
        now = timezone.now()
        if not (course.is_active and course.start_at <= now <= course.end_at):
            raise api_error(400, '완료 처리 가능한 수업이 아닙니다.')

    def _get_registration_or_404(self, user, course):
        try:
            return CourseRegistration.objects.get(user=user, course=course)
        except CourseRegistration.DoesNotExist:
            raise api_error(404, '수강 신청 이력이 없습니다.')
