from django.db.models import Exists, OuterRef
from django.db import transaction, IntegrityError
from courses.models import Course, CourseRegistration
from courses.serializers.course_list_serializer import CourseListSerializer
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_201_CREATED, HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND, HTTP_409_CONFLICT
from courses.serializers.course_enroll_serializer import CourseEnrollSerializer
from rest_framework.mixins import ListModelMixin
from assignment.config.pagination_config import CustomPagination
from rest_framework.viewsets import GenericViewSet
from payments.models import Payment
from rest_framework.permissions import IsAuthenticated


class CourseViewSet(ListModelMixin, GenericViewSet):
    serializer_class = CourseListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    def get_queryset(self):
        user = self.request.user
        queryset = self._base_queryset_with_registration_flag(user)
        queryset = self._apply_status_filter(queryset)
        queryset = self._apply_sorting(queryset)
        return queryset

    @action(detail=True, methods=['post'], url_path='complete')
    def complete(self, request, pk=None):
        course = self._get_course_or_404(pk)
        self._validate_course_is_completable(course)
        registration = self._get_registration_or_404(request.user, course)
        self._validate_registration_can_complete(registration)
        self._mark_registration_completed(registration)

        return Response({'registration_id': registration.id, 'status': 'completed'}, status=HTTP_200_OK)
    
    @action(detail=True, methods=['post'], url_path='enroll')
    def enroll(self, request, pk=None):
        serializer = CourseEnrollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        course = self._get_course_or_404(pk)
        self._validate_course_is_enrollable(course)
        self._ensure_not_already_registered(request.user, course)

        registration, payment = self._perform_enroll_transaction(request.user, course, serializer.validated_data)
        return Response(
            data={
                'registration_id': registration.id,
                'payment_id': payment.id,
                'status': 'paid',
            },
            status=HTTP_201_CREATED,
        )

    def _base_queryset_with_registration_flag(self, user):
        return Course.objects.all().annotate(
            is_registered=Exists(
                CourseRegistration.objects.filter(user=user, course_id=OuterRef('pk'))
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

    def _get_course_or_404(self, pk):
        try:
            return Course.objects.get(pk=pk)
        except Course.DoesNotExist:
            raise self._error(HTTP_404_NOT_FOUND, '존재하지 않는 수업입니다.')

    def _validate_course_is_enrollable(self, course):
        now = timezone.now()
        if not (course.is_active and course.start_at <= now <= course.end_at):
            raise self._error(HTTP_400_BAD_REQUEST, '수업 수강 가능한 수업이 아닙니다.')

    def _ensure_not_already_registered(self, user, course):
        if CourseRegistration.objects.filter(user=user, course=course).exists():
            raise self._error(HTTP_409_CONFLICT, '이미 수업 수강 신청된 수업입니다.')

    def _create_registration(self, user, course):
        return CourseRegistration.objects.create(user=user, course=course)

    def _create_payment(self, course_registration, data):
        return Payment.objects.create(
            course_registration=course_registration,
            amount=data['amount'],
            payment_method=data['payment_method'],
            status='paid',
        )

    def _perform_enroll_transaction(self, user, course, validated_data):
        with transaction.atomic():
            try:
                registration = self._create_registration(user, course)
            except IntegrityError:
                raise self._error(HTTP_409_CONFLICT, '이미 수업 수강 신청된 수업입니다.')
            try:
                payment = self._create_payment(registration, validated_data)
            except IntegrityError:
                raise self._error(HTTP_409_CONFLICT, '결제 정보가 이미 생성되었습니다.')
        return registration, payment

    def _validate_course_is_completable(self, course):
        now = timezone.now()
        if not (course.is_active and course.start_at <= now <= course.end_at):
            raise self._error(HTTP_400_BAD_REQUEST, '완료 처리 가능한 수업이 아닙니다.')

    def _get_registration_or_404(self, user, course):
        try:
            return CourseRegistration.objects.get(user=user, course=course)
        except CourseRegistration.DoesNotExist:
            raise self._error(HTTP_404_NOT_FOUND, '수강 신청 이력이 없습니다.')

    def _validate_registration_can_complete(self, registration):
        if registration.status == 'completed':
            raise self._error(HTTP_409_CONFLICT, '이미 완료된 수업입니다.')
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