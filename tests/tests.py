from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from rest_framework.serializers import ValidationError
from unittest.mock import patch
from django.db import IntegrityError
from tests.serializers.test_apply_serializer import TestApplySerializer

from tests.models import Test, TestRegistration
from payments.models import Payment


class TestViewSetTests(APITestCase):
    base_url = "/tests"

    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(email="t1@example.com", password="Str0ngP@ss!")
        token_res = self.client.post("/login", {"email": "t1@example.com", "password": "Str0ngP@ss!"}, format="json")
        self.assertEqual(token_res.status_code, status.HTTP_200_OK, token_res.data)
        self.access = token_res.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access}")

    def _make_test(self, title="Test", start_delta=-1, end_delta=1, is_active=True):
        now = timezone.now()
        return Test.objects.create(
            title=title,
            start_at=now + timedelta(days=start_delta),
            end_at=now + timedelta(days=end_delta),
            is_active=is_active,
        )

    def test_list_requires_auth(self):
        """
        인증 없으면 401
        """
        c = APIClient()
        res = c.get(self.base_url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_default_and_is_registered_annotation(self):
        """
        기본 목록 + is_registered 주석값 확인
        """
        t1 = self._make_test(title="Active-1", start_delta=-1, end_delta=1, is_active=True)
        t2 = self._make_test(title="Future", start_delta=1, end_delta=2, is_active=True)
        TestRegistration.objects.create(user=self.user, test=t1)

        res = self.client.get(self.base_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        items = res.data if isinstance(res.data, list) else res.data.get("results", [])
        ids = [item["id"] for item in items]
        self.assertIn(t1.id, ids)
        self.assertIn(t2.id, ids)

        d = {item["id"]: item for item in items}
        self.assertTrue(d[t1.id]["is_registered"])
        self.assertFalse(d[t2.id]["is_registered"])

    def test_filter_status_available(self):
        """
        사용 가능 필터: 활성 + 기간 내 + 미등록만 노출
        """
        available = self._make_test(title="Available", start_delta=-1, end_delta=1, is_active=True)
        registered = self._make_test(title="Registered", start_delta=-1, end_delta=1, is_active=True)
        TestRegistration.objects.create(user=self.user, test=registered)
        future = self._make_test(title="Future", start_delta=1, end_delta=2, is_active=True)
        inactive = self._make_test(title="Inactive", start_delta=-1, end_delta=1, is_active=False)

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
        인기 정렬: registrations_count 내림차순(동률 시 created_at 내림차순)
        """
        t1 = self._make_test(title="T1", start_delta=-1, end_delta=1)
        t2 = self._make_test(title="T2", start_delta=-1, end_delta=1)
        u2 = self.User.objects.create_user(email="t2@example.com", password="Str0ngP@ss!")
        u3 = self.User.objects.create_user(email="t3@example.com", password="Str0ngP@ss!")
        TestRegistration.objects.create(user=self.user, test=t1)
        TestRegistration.objects.create(user=u2, test=t2)
        TestRegistration.objects.create(user=u3, test=t2)

        res = self.client.get(f"{self.base_url}?sort=popular")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        items = res.data if isinstance(res.data, list) else res.data.get("results", [])
        ids = [item["id"] for item in items]
        self.assertTrue(ids.index(t2.id) < ids.index(t1.id))

    def test_apply_success(self):
        """
        정상 신청 시 registration/payment 생성 및 상태 확인
        """
        test = self._make_test(title="Apply OK", start_delta=-1, end_delta=1, is_active=True)
        res = self.client.post(f"{self.base_url}/{test.id}/apply", {"amount": 10000, "payment_method": "card"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertIn("registration_id", res.data)
        self.assertIn("payment_id", res.data)
        self.assertEqual(res.data["status"], "paid")

        reg = TestRegistration.objects.get(id=res.data["registration_id"])
        self.assertEqual(reg.user, self.user)
        self.assertEqual(reg.test, test)

        pay = Payment.objects.get(id=res.data["payment_id"])
        self.assertEqual(pay.test_registration_id, reg.id)
        self.assertIsNone(pay.course_registration_id)
        self.assertEqual(pay.status, "paid")

        test.refresh_from_db()
        self.assertEqual(test.registrations_count, 1)

    def test_apply_test_not_found(self):
        """
        존재하지 않는 시험 신청 시 404
        """
        res = self.client.post(f"{self.base_url}/999999/apply", {"amount": 10000, "payment_method": "card"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_apply_not_active_or_time(self):
        """
        비활성/기간 외 시험 신청 시 400
        """
        inactive = self._make_test(title="Inactive", start_delta=-1, end_delta=1, is_active=False)
        r1 = self.client.post(f"{self.base_url}/{inactive.id}/apply", {"amount": 10000, "payment_method": "card"}, format="json")
        self.assertEqual(r1.status_code, status.HTTP_400_BAD_REQUEST)

        future = self._make_test(title="Future", start_delta=1, end_delta=2, is_active=True)
        r2 = self.client.post(f"{self.base_url}/{future.id}/apply", {"amount": 10000, "payment_method": "card"}, format="json")
        self.assertEqual(r2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_apply_already_registered(self):
        """
        중복 신청 시 409
        """
        test = self._make_test(title="Dup", start_delta=-1, end_delta=1, is_active=True)
        TestRegistration.objects.create(user=self.user, test=test)
        res = self.client.post(f"{self.base_url}/{test.id}/apply", {"amount": 10000, "payment_method": "card"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)

    def test_apply_invalid_payment_method(self):
        """
        잘못된 결제수단 시 400
        """
        test = self._make_test(title="Invalid PM", start_delta=-1, end_delta=1, is_active=True)
        res = self.client.post(f"{self.base_url}/{test.id}/apply", {"amount": 10000, "payment_method": "unknown"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("payment_method", res.data)

    def test_complete_success(self):
        """
        완료 처리 성공 시 상태/attempted_at 갱신
        """
        test = self._make_test(title="Complete OK", start_delta=-1, end_delta=1, is_active=True)
        reg = TestRegistration.objects.create(user=self.user, test=test, status="registered")
        res = self.client.post(f"{self.base_url}/{test.id}/complete", {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        reg.refresh_from_db()
        self.assertEqual(reg.status, "completed")
        self.assertIsNotNone(reg.attempted_at)

    def test_complete_no_registration(self):
        """
        신청 이력 없을 때 404
        """
        test = self._make_test(title="No Reg", start_delta=-1, end_delta=1, is_active=True)
        res = self.client.post(f"{self.base_url}/{test.id}/complete", {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_complete_already_completed(self):
        """
        이미 완료된 신청 409
        """
        test = self._make_test(title="Already Done", start_delta=-1, end_delta=1, is_active=True)
        TestRegistration.objects.create(user=self.user, test=test, status="completed")
        res = self.client.post(f"{self.base_url}/{test.id}/complete", {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)

    def test_complete_cancelled(self):
        """
        취소된 신청 완료 불가 400
        """
        test = self._make_test(title="Cancelled", start_delta=-1, end_delta=1, is_active=True)
        TestRegistration.objects.create(user=self.user, test=test, status="cancelled")
        res = self.client.post(f"{self.base_url}/{test.id}/complete", {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_complete_not_active_or_time(self):
        """
        비활성/기간 외 완료 불가 400
        """
        inactive = self._make_test(title="Inactive", start_delta=-1, end_delta=1, is_active=False)
        TestRegistration.objects.create(user=self.user, test=inactive, status="registered")
        r1 = self.client.post(f"{self.base_url}/{inactive.id}/complete", {}, format="json")
        self.assertEqual(r1.status_code, status.HTTP_400_BAD_REQUEST)

        future = self._make_test(title="Future", start_delta=1, end_delta=2, is_active=True)
        TestRegistration.objects.create(user=self.user, test=future, status="registered")
        r2 = self.client.post(f"{self.base_url}/{future.id}/complete", {}, format="json")
        self.assertEqual(r2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_apply_registration_integrity_error(self):
        """
        트랜잭션 내 등록 생성 단계에서 IntegrityError 발생 시 409 반환
        """
        test = self._make_test(title="IE Reg", start_delta=-1, end_delta=1, is_active=True)
        with patch("tests.views.test_viewset.TestViewSet._create_registration", side_effect=IntegrityError()):
            res = self.client.post(
                f"{self.base_url}/{test.id}/apply",
                {"amount": 10000, "payment_method": "card"},
                format="json",
            )
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)

    def test_apply_payment_integrity_error(self):
        """
        트랜잭션 내 결제 생성 단계에서 IntegrityError 발생 시 409 반환
        """
        test = self._make_test(title="IE Pay", start_delta=-1, end_delta=1, is_active=True)
        with patch("tests.views.test_viewset.TestViewSet._create_payment", side_effect=IntegrityError()):
            res = self.client.post(
                f"{self.base_url}/{test.id}/apply",
                {"amount": 10000, "payment_method": "card"},
                format="json",
            )
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)

    def test_apply_amount_zero_invalid(self):
        """
        amount=0이면 직렬화기 검증으로 400 반환
        """
        test = self._make_test(title="Amount Zero", start_delta=-1, end_delta=1, is_active=True)
        res = self.client.post(
            f"{self.base_url}/{test.id}/apply",
            {"amount": 0, "payment_method": "card"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("amount", res.data)

    def test_serializer_validate_amount_and_method_success(self):
        """
        직렬화기 validator 정상 경로 커버리지 확보
        """
        s = TestApplySerializer(data={"amount": 1234, "payment_method": "card"})
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["amount"], 1234)

    def test_direct_validate_payment_method_raises(self):
        """
        커스텀 validator 메서드를 직접 호출하여 raise 라인을 커버한다.
        """
        ser = TestApplySerializer()
        with self.assertRaises(ValidationError):
            ser.validate_payment_method("unknown")

    def test_direct_validate_amount_raises(self):
        """
        커스텀 amount validator의 raise 라인을 직접 커버한다.
        """
        ser = TestApplySerializer()
        with self.assertRaises(ValidationError):
            ser.validate_amount(0)