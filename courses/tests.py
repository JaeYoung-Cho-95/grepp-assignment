from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from rest_framework.serializers import ValidationError

from courses.models import Course, CourseRegistration
from payments.models import Payment
from unittest.mock import patch
from django.db import IntegrityError
from courses.serializers.course_enroll_serializer import CourseEnrollSerializer


class CourseViewSetTests(APITestCase):
    base_url = "/courses"

    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(email="u1@example.com", password="Str0ngP@ss!")
        token_res = self.client.post("/login", {"email": "u1@example.com", "password": "Str0ngP@ss!"}, format="json")
        self.assertEqual(token_res.status_code, status.HTTP_200_OK, token_res.data)
        self.access = token_res.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access}")

    def _make_course(self, title="Course", start_delta=-1, end_delta=1, is_active=True):
        now = timezone.now()
        return Course.objects.create(
            title=title,
            start_at=now + timedelta(days=start_delta),
            end_at=now + timedelta(days=end_delta),
            is_active=is_active,
        )

    def test_list_requires_auth(self):
        """
        인증 없으면 401을 반환한다.
        """
        c = APIClient() 
        res = c.get(self.base_url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_default_and_is_registered_annotation(self):
        """
        기본 목록 조회 시 현재 사용자 등록 여부(is_registered)가 올바르게 츨력된다.
        """
        c1 = self._make_course(title="Active-1", start_delta=-1, end_delta=1, is_active=True)
        c2 = self._make_course(title="Future", start_delta=1, end_delta=2, is_active=True)
        CourseRegistration.objects.create(user=self.user, course=c1)

        res = self.client.get(self.base_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        items = res.data if isinstance(res.data, list) else res.data.get("results", [])
        ids = [item["id"] for item in items]
        self.assertIn(c1.id, ids)
        self.assertIn(c2.id, ids)

        d_by_id = {item["id"]: item for item in items}
        self.assertTrue(d_by_id[c1.id]["is_registered"])
        self.assertFalse(d_by_id[c2.id]["is_registered"])

    def test_filter_status_available(self):
        """
        status=available 쿼리로 활성+기간 내+미등록 항목만 반환한다.
        """
        available = self._make_course(title="Available", start_delta=-1, end_delta=1, is_active=True)
        registered = self._make_course(title="Registered", start_delta=-1, end_delta=1, is_active=True)
        CourseRegistration.objects.create(user=self.user, course=registered)

        future = self._make_course(title="Future", start_delta=1, end_delta=2, is_active=True)
        inactive = self._make_course(title="Inactive", start_delta=-1, end_delta=1, is_active=False)

        res = self.client.get(f"{self.base_url}?status=available")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        items = res.data if isinstance(res.data, list) else res.data.get("results", [])
        ids = {item["id"] for item in items}
        self.assertIn(available.id, ids)
        self.assertNotIn(registered.id, ids)
        self.assertNotIn(future.id, ids)
        self.assertNotIn(inactive.id, ids)


    def test_sort_popular(self):
        """
        sort=popular 시 registrations_count 내림차순(동률 시 created_at 내림차순)으로 정렬된다.
        """
        c1 = self._make_course(title="C1", start_delta=-1, end_delta=1)
        c2 = self._make_course(title="C2", start_delta=-1, end_delta=1)

        u2 = self.User.objects.create_user(email="u2@example.com", password="Str0ngP@ss!")
        u3 = self.User.objects.create_user(email="u3@example.com", password="Str0ngP@ss!")
        CourseRegistration.objects.create(user=self.user, course=c1)
        CourseRegistration.objects.create(user=u2, course=c2)
        CourseRegistration.objects.create(user=u3, course=c2)

        res = self.client.get(f"{self.base_url}?sort=popular")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        items = res.data if isinstance(res.data, list) else res.data.get("results", [])
        ids = [item["id"] for item in items]

        self.assertTrue(ids.index(c2.id) < ids.index(c1.id))

    def test_enroll_success(self):
        """
        정상 신청 시 registration/payment가 생성되고 상태가 'paid'로 응답된다.
        """
        course = self._make_course(title="Enroll OK", start_delta=-1, end_delta=1, is_active=True)
        res = self.client.post(f"{self.base_url}/{course.id}/enroll", {"amount": 10000, "payment_method": "card"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertIn("registration_id", res.data)
        self.assertIn("payment_id", res.data)
        self.assertEqual(res.data["status"], "paid")

        reg = CourseRegistration.objects.get(id=res.data["registration_id"])
        self.assertEqual(reg.user, self.user)
        self.assertEqual(reg.course, course)

        pay = Payment.objects.get(id=res.data["payment_id"])
        self.assertEqual(pay.course_registration_id, reg.id)
        self.assertIsNone(pay.test_registration_id)
        self.assertEqual(pay.status, "paid")

        course.refresh_from_db()
        self.assertEqual(course.registrations_count, 1)

    def test_enroll_course_not_found(self):
        """
        존재하지 않는 코스에 신청하면 404를 반환한다.
        """
        res = self.client.post(f"{self.base_url}/999999/enroll", {"amount": 10000, "payment_method": "card"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_enroll_not_active_or_time(self):
        """
        비활성 또는 기간 외 코스 신청 시 400을 반환한다.
        """
        inactive = self._make_course(title="Inactive", start_delta=-1, end_delta=1, is_active=False)
        res1 = self.client.post(f"{self.base_url}/{inactive.id}/enroll", {"amount": 10000, "payment_method": "card"}, format="json")
        self.assertEqual(res1.status_code, status.HTTP_400_BAD_REQUEST)

        future = self._make_course(title="Future", start_delta=1, end_delta=2, is_active=True)
        res2 = self.client.post(f"{self.base_url}/{future.id}/enroll", {"amount": 10000, "payment_method": "card"}, format="json")
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_enroll_already_registered(self):
        """
        이미 신청된 코스에 재신청 시 409를 반환한다.
        """
        course = self._make_course(title="Dup", start_delta=-1, end_delta=1, is_active=True)
        CourseRegistration.objects.create(user=self.user, course=course)
        res = self.client.post(f"{self.base_url}/{course.id}/enroll", {"amount": 10000, "payment_method": "card"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)

    def test_enroll_invalid_payment_method(self):
        """
        잘못된 결제수단으로 신청 시 400을 반환한다.
        """
        course = self._make_course(title="Invalid PM", start_delta=-1, end_delta=1, is_active=True)
        res = self.client.post(f"{self.base_url}/{course.id}/enroll", {"amount": 10000, "payment_method": "unknown"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("payment_method", res.data)

    def test_complete_success(self):
        """
        완료 처리 성공 시 registration.status='completed', attempted_at이 설정된다.
        """
        course = self._make_course(title="Complete OK", start_delta=-1, end_delta=1, is_active=True)
        reg = CourseRegistration.objects.create(user=self.user, course=course, status="registered")

        res = self.client.post(f"{self.base_url}/{course.id}/complete", {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        reg.refresh_from_db()
        self.assertEqual(reg.status, "completed")
        self.assertIsNotNone(reg.attempted_at)

    def test_complete_no_registration(self):
        """
        신청 이력이 없을 때 완료 요청 시 404를 반환한다.
        """
        course = self._make_course(title="No Reg", start_delta=-1, end_delta=1, is_active=True)
        res = self.client.post(f"{self.base_url}/{course.id}/complete", {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_complete_already_completed(self):
        """
        이미 완료된 신청에 대해 완료 요청 시 409를 반환한다.
        """
        course = self._make_course(title="Already Done", start_delta=-1, end_delta=1, is_active=True)
        reg = CourseRegistration.objects.create(user=self.user, course=course, status="completed")
        res = self.client.post(f"{self.base_url}/{course.id}/complete", {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)

    def test_complete_cancelled(self):
        """
        취소된 신청에 대해 완료 요청 시 400을 반환한다.
        """
        course = self._make_course(title="Cancelled", start_delta=-1, end_delta=1, is_active=True)
        reg = CourseRegistration.objects.create(user=self.user, course=course, status="cancelled")
        res = self.client.post(f"{self.base_url}/{course.id}/complete", {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_complete_not_active_or_time(self):
        """
        비활성 또는 기간 외 코스에 대해 완료 요청 시 400을 반환한다.
        """
        inactive = self._make_course(title="Inactive", start_delta=-1, end_delta=1, is_active=False)
        CourseRegistration.objects.create(user=self.user, course=inactive, status="registered")
        res1 = self.client.post(f"{self.base_url}/{inactive.id}/complete", {}, format="json")
        self.assertEqual(res1.status_code, status.HTTP_400_BAD_REQUEST)

        future = self._make_course(title="Future", start_delta=1, end_delta=2, is_active=True)
        CourseRegistration.objects.create(user=self.user, course=future, status="registered")
        res2 = self.client.post(f"{self.base_url}/{future.id}/complete", {}, format="json")
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_enroll_registration_integrity_error(self):
        """
        트랜잭션 내 등록 생성 시 무결성 에러 발생 → 409
        """
        course = self._make_course(title="IE Reg", start_delta=-1, end_delta=1, is_active=True)
        with patch("courses.views.course_viewset.CourseViewSet._create_registration", side_effect=IntegrityError()):
            res = self.client.post(
                f"{self.base_url}/{course.id}/enroll",
                {"amount": 10000, "payment_method": "card"},
                format="json",
            )
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("이미 수업 수강 신청된 수업입니다.", res.data.get("detail", ""))

    def test_enroll_payment_integrity_error(self):
        """
        트랜잭션 내 결제 생성 시 무결성 에러 발생 → 409
        """
        course = self._make_course(title="IE Pay", start_delta=-1, end_delta=1, is_active=True)
        with patch("courses.views.course_viewset.CourseViewSet._create_payment", side_effect=IntegrityError()):
            res = self.client.post(
                f"{self.base_url}/{course.id}/enroll",
                {"amount": 10000, "payment_method": "card"},
                format="json",
            )
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("결제 정보가 이미 생성되었습니다.", res.data.get("detail", ""))

    def test_enroll_invalid_amount_zero(self):
        """
        amount=0이면 400 반환(필드 수준 min_value 또는 커스텀 validator 중 하나로 차단)
        """
        course = self._make_course(title="Amount Zero", start_delta=-1, end_delta=1, is_active=True)
        res = self.client.post(
            f"{self.base_url}/{course.id}/enroll",
            {"amount": 0, "payment_method": "card"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("amount", res.data)


    def test_serializer_validate_amount_and_method_success(self):
        """
        직렬화기 개별 validator의 정상 경로도 실행
        """
        s = CourseEnrollSerializer(data={"amount": 1234, "payment_method": "card"})
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["amount"], 1234)

    def test_direct_validate_payment_method_raises(self):
        """
        커스텀 validator 메서드를 직접 호출하여 raise 라인을 커버한다.
        """
        ser = CourseEnrollSerializer()
        with self.assertRaises(ValidationError):
            ser.validate_payment_method("unknown")

    def test_direct_validate_amount_raises(self):
        """
        커스텀 amount validator의 raise 라인을 직접 커버한다.
        """
        ser = CourseEnrollSerializer()
        with self.assertRaises(ValidationError):
            ser.validate_amount(0)