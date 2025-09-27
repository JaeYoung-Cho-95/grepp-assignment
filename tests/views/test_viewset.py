from django.db.models import Exists, OuterRef, Q
from rest_framework import mixins, permissions, viewsets
from tests.models import Test, TestRegistration
from tests.serializers.test_list_serializer import TestListSerializer
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from tests.serializers.test_apply_serializer import TestApplySerializer
from payments.models import Payment


class TestViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = TestListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Test.objects.all().annotate(
            is_registered=Exists(
                TestRegistration.objects.filter(user=user, test_id=OuterRef('pk'))
            ),
        )

        status_param = self.request.query_params.get('status')
        if status_param == 'available':
            now = timezone.now()
            qs = qs.filter(is_active=True, is_registered=False, start_at__lte=now, end_at__gte=now)

        sort = self.request.query_params.get('sort', 'created')
        if sort == 'popular':
            return qs.order_by('-registrations_count', '-created_at')
        return qs.order_by('-created_at')


    @action(detail=True, methods=['post'], url_path='apply')
    def post_queryset(self, request, pk=None):
        serializer = TestApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount = serializer.validated_data['amount']
        payment_method = serializer.validated_data['payment_method']

        try:
            test = Test.objects.get(pk=pk)
        except Test.DoesNotExist:
            return Response({'detail': '존재하지 않는 시험입니다.'}, status=status.HTTP_404_NOT_FOUND)

        now = timezone.now()
        if not (test.is_active and test.start_at <= now <= test.end_at):
            return Response({'detail': '응시 가능한 시험이 아닙니다.'}, status=status.HTTP_400_BAD_REQUEST)

        # 이미 응시 신청 여부 확인
        exists = TestRegistration.objects.filter(user=request.user, test=test).exists()
        if exists:
            return Response({'detail': '이미 응시 신청된 시험입니다.'}, status=status.HTTP_409_CONFLICT)

        with transaction.atomic():
            # 신청 생성
            test_registration = TestRegistration.objects.create(user=request.user, test=test)

            # 결제 생성 (OneToOne: test_registration만 채우고 course_registration은 비움)
            payment = Payment.objects.create(
                test_registration=test_registration,
                amount=amount,
                payment_method=payment_method,
                status='paid',
            )

        return Response({
            'registration_id': test_registration.id,
            'payment_id': payment.id,
            'status': 'paid',
        }, status=status.HTTP_201_CREATED)


    @action(detail=True, methods=['post'], url_path='complete')
    def complete(self, request, pk=None):
        try:
            test = Test.objects.get(pk=pk)
        except Test.DoesNotExist:
            return Response({'detail': '존재하지 않는 시험입니다.'}, status=status.HTTP_404_NOT_FOUND)

        now = timezone.now()
        if not (test.is_active and test.start_at <= now <= test.end_at):
            return Response({'detail': '응시 완료 가능한 시험이 아닙니다.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            registration = TestRegistration.objects.get(user=request.user, test=test)
        except TestRegistration.DoesNotExist:
            return Response({'detail': '응시 신청 이력이 없습니다.'}, status=status.HTTP_404_NOT_FOUND)

        if registration.status == 'completed':
            return Response({'detail': '이미 완료된 시험입니다.'}, status=status.HTTP_409_CONFLICT)
        if registration.status == 'cancelled':
            return Response({'detail': '취소된 신청은 완료할 수 없습니다.'}, status=status.HTTP_400_BAD_REQUEST)

        # 완료 처리
        registration.status = 'completed'
        if registration.attempted_at is None:
            registration.attempted_at = now
        registration.save(update_fields=['status', 'attempted_at'])

        return Response({
            'registration_id': registration.id,
            'status': 'completed',
        }, status=status.HTTP_200_OK)