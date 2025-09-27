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

def seed_courses(n=50_000, batch_size=10_000):
    now = timezone.now()
    existing = Course.objects.count()
    if existing >= n:
        print(f"Course 스킵: 이미 {existing}개 존재(목표 {n})")
        return
    to_create = n - existing
    print(f"Course 생성 시작: {to_create}개 (배치 {batch_size})")
    batch = []
    created_total = 0
    for i in range(existing, n):
        # 다양성: 일부는 과거/미래, 일부는 비활성
        start_at = now - timedelta(days=(i % 5))
        end_at = now + timedelta(days=((i % 10) + 1))
        is_active = (i % 10) != 0  # 약 90% 활성
        batch.append(Course(
            title=f"Course {i}",
            start_at=start_at,
            end_at=end_at,
            is_active=is_active,
        ))
        if len(batch) == batch_size:
            Course.objects.bulk_create(batch, batch_size=batch_size)
            created_total += len(batch)
            batch.clear()
            if created_total % 50_000 == 0:
                print(f"  진행 상황: {created_total}/{to_create} 생성")
    if batch:
        Course.objects.bulk_create(batch, batch_size=batch_size)
        created_total += len(batch)
    print(f"Course 생성 완료: {created_total}개")

def seed_tests(n=950_000, batch_size=10_000):
    now = timezone.now()
    existing = Test.objects.count()
    if existing >= n:
        print(f"Test 스킵: 이미 {existing}개 존재(목표 {n})")
        return
    to_create = n - existing
    print(f"Test 생성 시작: {to_create}개 (배치 {batch_size})")
    batch = []
    created_total = 0
    for i in range(existing, n):
        start_at = now - timedelta(days=(i % 3))
        end_at = now + timedelta(days=((i % 5) + 1))
        is_active = (i % 12) != 0  # 약 91.7% 활성
        batch.append(Test(
            title=f"Test {i}",
            start_at=start_at,
            end_at=end_at,
            is_active=is_active,
        ))
        if len(batch) == batch_size:
            Test.objects.bulk_create(batch, batch_size=batch_size)
            created_total += len(batch)
            batch.clear()
            if created_total % 100_000 == 0:
                print(f"  진행 상황: {created_total}/{to_create} 생성")
    if batch:
        Test.objects.bulk_create(batch, batch_size=batch_size)
        created_total += len(batch)
    print(f"Test 생성 완료: {created_total}개")

def main():
    ensure_admin()
    seed_users(n=10)
    # 대량 데이터 생성: 수업 5만, 시험 95만
    seed_courses(n=50_000, batch_size=10_000)
    seed_tests(n=950_000, batch_size=10_000)
    print("더미 데이터 생성 완료.")

if __name__ == "__main__":
    main()