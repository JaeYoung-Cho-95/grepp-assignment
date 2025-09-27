from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from courses.models import Course, CourseRegistration
from tests.models import Test, TestRegistration
from payments.models import Payment


class MePaymentsViewSetTests(APITestCase):
    base_url = "/me/payments"

    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(email="p1@example.com", password="Str0ngP@ss!")
        token_res = self.client.post("/login", {"email": "p1@example.com", "password": "Str0ngP@ss!"}, format="json")
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

    def _make_test(self, title="Test", start_delta=-1, end_delta=1, is_active=True):
        now = timezone.now()
        return Test.objects.create(
            title=title,
            start_at=now + timedelta(days=start_delta),
            end_at=now + timedelta(days=end_delta),
            is_active=is_active,
        )

    def _make_course_payment(self, user, course, amount=1000, status_value="paid", attempted=False, when=None):
        reg = CourseRegistration.objects.create(user=user, course=course, status="registered")
        if attempted:
            reg.attempted_at = timezone.now()
            reg.save(update_fields=["attempted_at"])
        paid_at = canceled_at = None
        if status_value == "paid":
            paid_at = when or timezone.now()
        elif status_value == "cancelled":
            canceled_at = when or timezone.now()
        return Payment.objects.create(
            course_registration=reg,
            amount=amount,
            payment_method="card",
            status=status_value,
            paid_at=paid_at,
            canceled_at=canceled_at,
        )

    def _make_test_payment(self, user, test, amount=1000, status_value="paid", attempted=False, when=None):
        reg = TestRegistration.objects.create(user=user, test=test, status="registered")
        if attempted:
            reg.attempted_at = timezone.now()
            reg.save(update_fields=["attempted_at"])
        paid_at = canceled_at = None
        if status_value == "paid":
            paid_at = when or timezone.now()
        elif status_value == "cancelled":
            canceled_at = when or timezone.now()
        return Payment.objects.create(
            test_registration=reg,
            amount=amount,
            payment_method="card",
            status=status_value,
            paid_at=paid_at,
            canceled_at=canceled_at,
        )

    def test_requires_auth(self):
        """
        인증 없으면 401
        """
        c = APIClient()
        res = c.get(self.base_url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_only_my_payments_and_ordering(self):
        """
        내 결제만 조회되고, 생성시간 내림차순(최신순) 정렬
        """
        course = self._make_course(title="C1")
        test = self._make_test(title="T1")

        p1 = self._make_course_payment(self.user, course, amount=1111)  # older
        p2 = self._make_test_payment(self.user, test, amount=2222)      # newer

        u2 = self.User.objects.create_user(email="p2@example.com", password="Str0ngP@ss!")
        other_course = self._make_course(title="Other")
        self._make_course_payment(u2, other_course, amount=3333)

        res = self.client.get(self.base_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        amounts = [item["amount"] for item in res.data]
        self.assertIn(1111, amounts)
        self.assertIn(2222, amounts)
        self.assertEqual(res.data[0]["amount"], 2222)

    def test_serializer_fields_target_item_title_attempted_at(self):
        """
        직렬화 필드: target/item_title/attempted_at 채워짐
        """
        course = self._make_course(title="Django 강의")
        test = self._make_test(title="모의고사 A")

        p_course = self._make_course_payment(self.user, course, amount=1111, attempted=True)
        p_test = self._make_test_payment(self.user, test, amount=2222, attempted=True)

        res = self.client.get(self.base_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        by_amount = {item["amount"]: item for item in res.data}

        self.assertEqual(by_amount[1111]["target"], "course")
        self.assertEqual(by_amount[1111]["item_title"], "Django 강의")
        self.assertIsNotNone(by_amount[1111]["attempted_at"])

        self.assertEqual(by_amount[2222]["target"], "test")
        self.assertEqual(by_amount[2222]["item_title"], "모의고사 A")
        self.assertIsNotNone(by_amount[2222]["attempted_at"])

    def test_filter_status_invalid(self):
        """
        허용되지 않은 status 값 → 400
        """
        res = self.client.get(f"{self.base_url}?status=pending")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", res.data)

    def test_filter_paid_with_date_range(self):
        """
        status=paid + 날짜 범위 → paid_at 기준 필터
        """
        course_old = self._make_course(title="C2-old")
        course_new = self._make_course(title="C2-new")
        day_2_ago = timezone.now() - timedelta(days=2)
        day_0 = timezone.now()

        self._make_course_payment(self.user, course_old, amount=1111, status_value="paid", when=day_2_ago)
        self._make_course_payment(self.user, course_new, amount=2222, status_value="paid", when=day_0)

        frm = (timezone.now() - timedelta(days=1)).date().isoformat()
        to = timezone.now().date().isoformat()

        res = self.client.get(f"{self.base_url}?status=paid&from={frm}&to={to}")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        amounts = [item["amount"] for item in res.data]
        self.assertIn(2222, amounts)
        self.assertNotIn(1111, amounts)

    def test_filter_cancelled_with_date_range(self):
        """
        status=cancelled + 날짜 범위 → canceled_at 기준 필터
        """
        test_old = self._make_test(title="T2-old")
        test_new = self._make_test(title="T2-new")
        day_3_ago = timezone.now() - timedelta(days=3)
        day_1_ago = timezone.now() - timedelta(days=1)

        self._make_test_payment(self.user, test_old, amount=1111, status_value="cancelled", when=day_3_ago)
        self._make_test_payment(self.user, test_new, amount=2222, status_value="cancelled", when=day_1_ago)

        frm = (timezone.now() - timedelta(days=2)).date().isoformat()
        to = timezone.now().date().isoformat()

        res = self.client.get(f"{self.base_url}?status=cancelled&from={frm}&to={to}")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        amounts = [item["amount"] for item in res.data]
        self.assertIn(2222, amounts)
        self.assertNotIn(1111, amounts)

    def test_filter_created_at_range_without_status(self):
        """
        status 미지정 + 날짜 범위 → created_at 기준 필터
        """
        course_old = self._make_course(title="C3-old")
        course_new = self._make_course(title="C3-new")

        p_old = self._make_course_payment(self.user, course_old, amount=1111)
        old_time = timezone.now() - timedelta(days=5)
        Payment.objects.filter(id=p_old.id).update(created_at=old_time)

        self._make_course_payment(self.user, course_new, amount=2222)

        frm = (timezone.now() - timedelta(days=1)).date().isoformat()
        to = timezone.now().date().isoformat()

        res = self.client.get(f"{self.base_url}?from={frm}&to={to}")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        amounts = [item["amount"] for item in res.data]
        self.assertIn(2222, amounts)
        self.assertNotIn(1111, amounts)

    def test_filter_date_parse_error(self):
        """
        날짜 파싱 오류 → 400
        """
        res = self.client.get(f"{self.base_url}?status=paid&from=2025-13-01")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("from/to", res.data)


class PaymentCancelViewSetTests(APITestCase):
    base_url = "/payments"

    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(email="owner@example.com", password="Str0ngP@ss!")
        token_res = self.client.post("/login", {"email": "owner@example.com", "password": "Str0ngP@ss!"}, format="json")
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

    def _make_test(self, title="Test", start_delta=-1, end_delta=1, is_active=True):
        now = timezone.now()
        return Test.objects.create(
            title=title,
            start_at=now + timedelta(days=start_delta),
            end_at=now + timedelta(days=end_delta),
            is_active=is_active,
        )

    def test_cancel_course_payment_success(self):
        """
        결제 취소 성공(수업): 신청/결제 CASCADE 삭제
        """
        course = self._make_course()
        reg = CourseRegistration.objects.create(user=self.user, course=course)
        pay = Payment.objects.create(course_registration=reg, amount=1000, payment_method="card", status="paid")

        res = self.client.post(f"{self.base_url}/{pay.id}/cancel", {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(res.data["detail"], "결제가 취소되었습니다.")
        self.assertEqual(res.data["deleted_registration_id"], reg.id)

        with self.assertRaises(CourseRegistration.DoesNotExist):
            CourseRegistration.objects.get(id=reg.id)
        with self.assertRaises(Payment.DoesNotExist):
            Payment.objects.get(id=pay.id)

    def test_cancel_test_payment_success(self):
        """
        결제 취소 성공(시험): 신청/결제 CASCADE 삭제
        """
        test = self._make_test()
        reg = TestRegistration.objects.create(user=self.user, test=test)
        pay = Payment.objects.create(test_registration=reg, amount=2000, payment_method="card", status="paid")

        res = self.client.post(f"{self.base_url}/{pay.id}/cancel", {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(res.data["deleted_registration_id"], reg.id)
        with self.assertRaises(TestRegistration.DoesNotExist):
            TestRegistration.objects.get(id=reg.id)
        with self.assertRaises(Payment.DoesNotExist):
            Payment.objects.get(id=pay.id)

    def test_cancel_not_found(self):
        """
        존재하지 않는 결제 → 404
        """
        res = self.client.post(f"{self.base_url}/999999/cancel", {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("존재하지 않는 결제입니다.", res.data.get("detail", ""))

    def test_cancel_forbidden_not_owner(self):
        """
        결제 소유자 아님 → 403
        """
        course = self._make_course()
        other = self.User.objects.create_user(email="notme@example.com", password="Str0ngP@ss!")
        reg = CourseRegistration.objects.create(user=other, course=course)
        pay = Payment.objects.create(course_registration=reg, amount=3000, payment_method="card", status="paid")

        res = self.client.post(f"{self.base_url}/{pay.id}/cancel", {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("본인의 결제만 취소할 수 있습니다.", res.data.get("detail", ""))

    def test_cancel_conflict_completed_registration(self):
        """
        완료된 신청은 취소 불가 → 409
        """
        course = self._make_course()
        reg = CourseRegistration.objects.create(user=self.user, course=course, status="completed")
        pay = Payment.objects.create(course_registration=reg, amount=4000, payment_method="card", status="paid")

        res = self.client.post(f"{self.base_url}/{pay.id}/cancel", {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("완료된 내역은 취소할 수 없습니다.", res.data.get("detail", ""))

        self.assertTrue(CourseRegistration.objects.filter(id=reg.id).exists())
        self.assertTrue(Payment.objects.filter(id=pay.id).exists())