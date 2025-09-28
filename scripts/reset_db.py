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
from django.db import connection, transaction

def main():
    # 대량 데이터 초기화에 적합: TRUNCATE로 연쇄 삭제 + 시퀀스 초기화
    tables = [
        'payments',
        'course_registrations',
        'test_registrations',
        'courses',
        'tests',
    ]
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE;"
            )
    print(f"TRUNCATE 완료: {', '.join(tables)} (RESTART IDENTITY CASCADE)")

    # 4) 사용자 삭제 (슈퍼유저는 보존)
    User = get_user_model()
    deleted = User.objects.filter(is_superuser=False).delete()
    print(f"User(슈퍼유저 제외) 삭제: {deleted}")

    print("DB 정리 완료.")

if __name__ == "__main__":
    main()