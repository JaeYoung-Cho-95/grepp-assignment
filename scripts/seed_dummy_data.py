import os
from datetime import timedelta
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "assignment.settings")

import django
django.setup()

from django.utils import timezone
from django.contrib.auth import get_user_model
from courses.models import Course
from tests.models import Test

def ensure_admin():
    User = get_user_model()
    admin_email = "admin@example.com"
    if not User.objects.filter(email=admin_email).exists():
        print("슈퍼유저 생성:", admin_email)
        User.objects.create_superuser(email=admin_email, password="admin1234")
    else:
        print("슈퍼유저 이미 존재:", admin_email)

def seed_users(n=10):
    User = get_user_model()
    users = []
    for i in range(1, n + 1):
        email = f"user{i:02d}@example.com"
        if not User.objects.filter(email=email).exists():
            user = User.objects.create_user(email=email, password="pass1234")
            users.append(user)
    print(f"User 생성 완료: {len(users)}개")

def seed_courses():
    now = timezone.now()
    data = [
        # active now
        ("파이썬 기초", now - timedelta(days=1), now + timedelta(days=7), True),
        ("Django 웹개발", now - timedelta(hours=2), now + timedelta(days=2), True),
        # future
        ("데이터분석 입문", now + timedelta(days=1), now + timedelta(days=10), True),
        ("비동기 프로그래밍", now + timedelta(days=3), now + timedelta(days=6), True),
        # past / inactive
        ("알고리즘 스터디", now - timedelta(days=10), now - timedelta(days=3), True),
        ("아키텍처 패턴", now - timedelta(days=5), now + timedelta(days=1), False),
    ]
    created = 0
    for title, start_at, end_at, is_active in data:
        if not Course.objects.filter(title=title, start_at=start_at, end_at=end_at).exists():
            Course.objects.create(
                title=title,
                start_at=start_at,
                end_at=end_at,
                is_active=is_active,
            )
            created += 1
    print(f"Course 생성 완료: {created}개")

def seed_tests():
    now = timezone.now()
    data = [
        # active now
        ("모의고사 A", now - timedelta(days=1), now + timedelta(days=1), True),
        ("모의고사 B", now - timedelta(hours=3), now + timedelta(hours=5), True),
        # future
        ("실전 모의고사 1회", now + timedelta(days=2), now + timedelta(days=3), True),
        ("실전 모의고사 2회", now + timedelta(days=5), now + timedelta(days=7), True),
        # past / inactive
        ("진단평가", now - timedelta(days=7), now - timedelta(days=6), True),
        ("레벨평가", now - timedelta(days=4), now + timedelta(hours=12), False),
    ]
    created = 0
    for title, start_at, end_at, is_active in data:
        if not Test.objects.filter(title=title, start_at=start_at, end_at=end_at).exists():
            Test.objects.create(
                title=title,
                start_at=start_at,
                end_at=end_at,
                is_active=is_active,
            )
            created += 1
    print(f"Test 생성 완료: {created}개")

def main():
    ensure_admin()
    seed_users(n=10)
    seed_courses()
    seed_tests()
    print("더미 데이터 생성 완료.")

if __name__ == "__main__":
    main()