from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from courses.models import Course, CourseRegistration
from payments.models import Payment


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
        # c1에 현재 사용자 등록
        CourseRegistration.objects.create(user=self.user, course=c1)

        res = self.client.get(self.base_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        ids = [item["id"] for item in res.data]
        self.assertIn(c1.id, ids)
        self.assertIn(c2.id, ids)

        d_by_id = {item["id"]: item for item in res.data}
        self.assertTrue(d_by_id[c1.id]["is_registered"])
        self.assertFalse(d_by_id[c2.id]["is_registered"])

    def test_filter_status_available(self):
        """
        status=available 쿼리로 활성+기간 내+미등록 항목만 반환한다.
        """
        # 사용 가능: is_active=True 이고 now 범위 안이며, 아직 미등록
        available = self._make_course(title="Available", start_delta=-1, end_delta=1, is_active=True)
        # 이미 등록된 코스
        registered = self._make_course(title="Registered", start_delta=-1, end_delta=1, is_active=True)
        CourseRegistration.objects.create(user=self.user, course=registered)
        # 시간 범위 밖
        future = self._make_course(title="Future", start_delta=1, end_delta=2, is_active=True)
        # 비활성
        inactive = self._make_course(title="Inactive", start_delta=-1, end_delta=1, is_active=False)

        res = self.client.get(f"{self.base_url}?status=available")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        ids = {item["id"] for item in res.data}
        self.assertIn(available.id, ids)
        self.assertNotIn(registered.id, ids)
        self.assertNotIn(future.id, ids)
        self.assertNotIn(inactive.id, ids)


    def test_sort_popular(self):
        """
        sort=popular 시 registrations_count 내림차순(동률 시 created_at 내림차순)으로 정렬된다.
        """
        # 인기 정렬은 registrations_count 내림차순, 동률이면 created_at 내림차순
        c1 = self._make_course(title="C1", start_delta=-1, end_delta=1)
        c2 = self._make_course(title="C2", start_delta=-1, end_delta=1)

        # 다른 사용자 2명 추가하여 c2에 2명 등록, c1에 1명 등록
        u2 = self.User.objects.create_user(email="u2@example.com", password="Str0ngP@ss!")
        u3 = self.User.objects.create_user(email="u3@example.com", password="Str0ngP@ss!")
        CourseRegistration.objects.create(user=self.user, course=c1)
        CourseRegistration.objects.create(user=u2, course=c2)
        CourseRegistration.objects.create(user=u3, course=c2)

        res = self.client.get(f"{self.base_url}?sort=popular")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in res.data]
        # c2가 더 인기 있으므로 앞에 와야 함
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
        # 비활성
        inactive = self._make_course(title="Inactive", start_delta=-1, end_delta=1, is_active=False)
        res1 = self.client.post(f"{self.base_url}/{inactive.id}/enroll", {"amount": 10000, "payment_method": "card"}, format="json")
        self.assertEqual(res1.status_code, status.HTTP_400_BAD_REQUEST)

        # 시간 범위 밖(미시작)
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
        # 비활성
        inactive = self._make_course(title="Inactive", start_delta=-1, end_delta=1, is_active=False)
        CourseRegistration.objects.create(user=self.user, course=inactive, status="registered")
        res1 = self.client.post(f"{self.base_url}/{inactive.id}/complete", {}, format="json")
        self.assertEqual(res1.status_code, status.HTTP_400_BAD_REQUEST)

        # 시간 범위 밖(미시작)
        future = self._make_course(title="Future", start_delta=1, end_delta=2, is_active=True)
        CourseRegistration.objects.create(user=self.user, course=future, status="registered")
        res2 = self.client.post(f"{self.base_url}/{future.id}/complete", {}, format="json")
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)