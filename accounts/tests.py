from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from django.test import TestCase

User = get_user_model()

class SignUpAPITests(APITestCase):
    url = "/signup"

    def test_signup_success(self):
        """
        유효한 이메일/강한 비밀번호 → 201, 응답에 id/email/created_at 포함, 비밀번호 해싱 확인
        """   
        data = {"email": "user1@example.com", "password": "Str0ngP@ssw0rd!"}
        res = self.client.post(self.url, data, format="json")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", res.data)
        self.assertEqual(res.data["email"], data["email"])
        self.assertIn("created_at", res.data)

        user = User.objects.get(email=data["email"])
        self.assertTrue(user.check_password(data["password"]))

    def test_signup_duplicate_email(self):
        """
        기존 사용자와 이메일 중복 → 400, 'email' 에러 키 존재
        """        
        User.objects.create_user(email="dup@example.com", password="Str0ngP@ss1!")
        data = {"email": "dup@example.com", "password": "An0therStr0ng!"}
        res = self.client.post(self.url, data, format="json")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", res.data)
        

    def test_signup_invalid_email(self):
        """
        잘못된 이메일 포맷 → 400, 'email' 에러 키 존재
        """        
        data = {"email": "not-an-email", "password": "Str0ngP@ssw0rd!"}
        res = self.client.post(self.url, data, format="json")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", res.data)

    def test_signup_weak_password(self):
        """
        약한 비밀번호 → 400, 'password' 에러 키 존재
        """        
        data = {"email": "user2@example.com", "password": "123"}
        res = self.client.post(self.url, data, format="json")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", res.data)

    def test_method_not_allowed(self):
        """
        GET 메서드 요청 → 405
        """        
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class UserManagerTests(TestCase):
    def setUp(self):
        self.User = get_user_model()

    def test_create_user_success(self):
        u = self.User.objects.create_user(email="m1@example.com", password="Str0ngP@ss!")
        self.assertEqual(u.email, "m1@example.com")
        self.assertTrue(u.check_password("Str0ngP@ss!"))

    def test_create_user_requires_email(self):
        with self.assertRaisesMessage(ValueError, '이메일은 필수입니다'):
            self.User.objects.create_user(email="", password="x")

    def test_create_user_requires_password(self):
        with self.assertRaisesMessage(ValueError, '비밀번호는 필수입니다'):
            self.User.objects.create_user(email="m2@example.com", password="")

    def test_create_superuser_success(self):
        su = self.User.objects.create_superuser(email="admin@example.com", password="Adm1nP@ss!")
        self.assertTrue(su.is_staff)
        self.assertTrue(su.is_superuser)

    def test_create_superuser_requires_is_staff_true(self):
        with self.assertRaisesMessage(ValueError, '슈퍼유저는 is_staff=True여야 합니다'):
            self.User.objects.create_superuser(email="a@example.com", password="x", is_staff=False)

    def test_create_superuser_requires_is_superuser_true(self):
        with self.assertRaisesMessage(ValueError, '슈퍼유저는 is_superuser=True여야 합니다'):
            self.User.objects.create_superuser(email="b@example.com", password="x", is_superuser=False)