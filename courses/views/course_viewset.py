from django.db.models import Exists, OuterRef, Q
from rest_framework import mixins, permissions, viewsets
from courses.models import Course, CourseRegistration
from courses.serializers.course_list_serializer import CourseListSerializer
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from courses.serializers.course_enroll_serializer import CourseEnrollSerializer
from payments.models import Payment

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


    @action(detail=True, methods=['post'], url_path='enroll')
    def post_queryset(self, request, pk=None):
        serializer = CourseEnrollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount = serializer.validated_data['amount']
        payment_method = serializer.validated_data['payment_method']

        try:
            course = Course.objects.get(pk=pk)
        except Course.DoesNotExist:
            return Response({'detail': '존재하지 않는 수업입니다.'}, status=status.HTTP_404_NOT_FOUND)

        now = timezone.now()
        if not (course.is_active and course.start_at <= now <= course.end_at):
            return Response({'detail': '수업 수강 가능한 수업이 아닙니다.'}, status=status.HTTP_400_BAD_REQUEST)

        # 이미 수업 수강 신청 여부 확인
        exists = CourseRegistration.objects.filter(user=request.user, course=course).exists()
        if exists:
            return Response({'detail': '이미 수업 수강 신청된 수업입니다.'}, status=status.HTTP_409_CONFLICT)

        with transaction.atomic():
            # 수업 수강 신청 생성
            course_registration = CourseRegistration.objects.create(user=request.user, course=course)

            # 결제 생성 (OneToOne: course_registration만 채우고 course_registration은 비움)
            payment = Payment.objects.create(
                course_registration=course_registration,
                amount=amount,
                payment_method=payment_method,
                status='paid',
            )

        return Response({
            'registration_id': course_registration.id,
            'payment_id': payment.id,
            'status': 'paid',
        }, status=status.HTTP_201_CREATED)


    @action(detail=True, methods=['post'], url_path='complete')
    def complete(self, request, pk=None):
        try:
            course = Course.objects.get(pk=pk)
        except Course.DoesNotExist:
            return Response({'detail': '존재하지 않는 수업입니다.'}, status=status.HTTP_404_NOT_FOUND)

        now = timezone.now()
        if not (course.is_active and course.start_at <= now <= course.end_at):
            return Response({'detail': '완료 처리 가능한 수업이 아닙니다.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            registration = CourseRegistration.objects.get(user=request.user, course=course)
        except CourseRegistration.DoesNotExist:
            return Response({'detail': '수강 신청 이력이 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        if registration.status == 'completed':
            return Response({'detail': '이미 완료된 수업입니다.'}, status=status.HTTP_409_CONFLICT)
        if registration.status == 'cancelled':
            return Response({'detail': '취소된 신청은 완료할 수 없습니다.'}, status=status.HTTP_400_BAD_REQUEST)

        registration.status = 'completed'
        if registration.attempted_at is None:
            registration.attempted_at = now
        registration.save(update_fields=['status', 'attempted_at', 'updated_at'])

        return Response({
            'registration_id': registration.id,
            'status': 'completed',
        }, status=status.HTTP_200_OK)