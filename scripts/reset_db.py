import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "assignment.settings")

import django
django.setup()

from django.contrib.auth import get_user_model
from courses.models import Course, CourseRegistration
from tests.models import Test, TestRegistration
from payments.models import Payment

def main():
    # 1) 결제 삭제 (OneToOne → 등록 삭제 전)
    deleted = Payment.objects.all().delete()
    print(f"Payment 삭제: {deleted}")

    # 2) 등록 삭제
    deleted = CourseRegistration.objects.all().delete()
    print(f"CourseRegistration 삭제: {deleted}")
    deleted = TestRegistration.objects.all().delete()
    print(f"TestRegistration 삭제: {deleted}")

    # 3) 코어 테이블 삭제
    deleted = Course.objects.all().delete()
    print(f"Course 삭제: {deleted}")
    deleted = Test.objects.all().delete()
    print(f"Test 삭제: {deleted}")

    # 4) 사용자 삭제 (슈퍼유저는 보존)
    User = get_user_model()
    deleted = User.objects.filter(is_superuser=False).delete()
    print(f"User(슈퍼유저 제외) 삭제: {deleted}")

    print("DB 정리 완료.")

if __name__ == "__main__":
    main()