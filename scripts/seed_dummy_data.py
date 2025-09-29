import os
from datetime import timedelta
import random
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
from django.contrib.auth.hashers import make_password
from courses.models import Course, CourseRegistration
from tests.models import Test, TestRegistration
from payments.models import Payment
from django.db import connection

def random_recent_datetime(max_days=60):
    now_ts = timezone.now()
    seconds = random.randint(0, max_days * 24 * 3600)
    return now_ts - timedelta(seconds=seconds)

def ensure_admin():
    User = get_user_model()
    admin_email = "admin@example.com"
    if not User.objects.filter(email=admin_email).exists():
        print("슈퍼유저 생성:", admin_email)
        User.objects.create_superuser(email=admin_email, password="admin1234")
    else:
        print("슈퍼유저 이미 존재:", admin_email)

def seed_users(n=50_000, batch_size=10_000):
    User = get_user_model()
    password_hash = make_password("pass1234")
    batch = []
    created_total = 0
    for i in range(1, n + 1):
        email = f"user{i:06d}@example.com"
        batch.append(User(email=email, password=password_hash))
        if len(batch) == batch_size:
            User.objects.bulk_create(batch, ignore_conflicts=True, batch_size=batch_size)
            created_total += len(batch)
            batch.clear()
    if batch:
        User.objects.bulk_create(batch, ignore_conflicts=True, batch_size=batch_size)
        created_total += len(batch)
    print(f"User 생성 완료(시도 기준): {created_total}개 (중복은 ignore_conflicts로 무시)")

def seed_courses(n=1_000_000, batch_size=10_000):
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
            if created_total % 100_000 == 0:
                print(f"  진행 상황: {created_total}/{to_create} 생성")
    if batch:
        Course.objects.bulk_create(batch, batch_size=batch_size)
        created_total += len(batch)
    print(f"Course 생성 완료: {created_total}개")

def seed_tests(n=1_000_000, batch_size=10_000):
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


def seed_course_registrations_and_payments(users_limit=50_000, registrations_per_user=3, batch_size=5_000):
    User = get_user_model()
    now = timezone.now()
    user_ids = list(User.objects.order_by('id').values_list('id', flat=True)[:users_limit])
    available_course_ids = list(
        Course.objects.filter(is_active=True, start_at__lte=now, end_at__gte=now)
        .order_by('id')
        .values_list('id', flat=True)
    )
    if not available_course_ids:
        print("CourseRegistration 스킵: 사용 가능한 수업이 없습니다.")
        return
    # 코스 기간 메타 캐시
    course_meta = {
        row['id']: (row['start_at'], row['end_at'])
        for row in Course.objects.filter(id__in=available_course_ids).values('id', 'start_at', 'end_at')
    }
    # 상태 분포
    reg_statuses = ['registered', 'in_progress', 'completed', 'cancelled']
    reg_weights = [60, 20, 15, 5]
    # 인기/일반 구간으로 나눠 등록 수 편차를 크게 만듦
    hot_size = max(1, min(len(available_course_ids), 500))
    warm_size = max(1, min(len(available_course_ids) - hot_size, 2000))
    hot_ids = available_course_ids[:hot_size]
    warm_ids = available_course_ids[hot_size:hot_size + warm_size]
    rest_ids = available_course_ids[hot_size + warm_size:]

    total_regs_created = 0
    total_payments_created = 0
    for start in range(0, len(user_ids), batch_size):
        batch_user_ids = user_ids[start:start + batch_size]
        reg_objs = []
        planned_pairs = []  # (user_id, course_id, status)
        for idx, user_id in enumerate(batch_user_ids, start=start):
            for j in range(registrations_per_user):
                bucket = random.choices(['hot', 'warm', 'rest'], weights=[70, 25, 5], k=1)[0]
                if bucket == 'hot' and hot_ids:
                    course_id = random.choice(hot_ids)
                elif bucket == 'warm' and warm_ids:
                    course_id = random.choice(warm_ids)
                elif rest_ids:
                    course_id = random.choice(rest_ids)
                else:
                    course_id = available_course_ids[(idx * 7 + j) % len(available_course_ids)]
                status = random.choices(reg_statuses, weights=reg_weights, k=1)[0]
                attempted_at = None
                if status == 'completed':
                    c_start, c_end = course_meta.get(course_id, (now, now))
                    end_bound = min(c_end, now)
                    if c_start < end_bound:
                        # 무작위 완료 시각
                        delta_sec = int((end_bound - c_start).total_seconds())
                        attempted_at = c_start + timedelta(seconds=random.randint(0, max(delta_sec, 1)))
                planned_pairs.append((user_id, course_id, status))
                reg_objs.append(CourseRegistration(
                    user_id=user_id,
                    course_id=course_id,
                    status=status,
                    attempted_at=attempted_at,
                ))

        created = CourseRegistration.objects.bulk_create(
            reg_objs,
            ignore_conflicts=True,
            batch_size=batch_size,
        )
        total_regs_created += len(created)

        pair_course_ids = [c for (_, c, _) in planned_pairs]
        regs_without_payment_qs = CourseRegistration.objects.filter(
            user_id__in=batch_user_ids,
            course_id__in=set(pair_course_ids),
            payment__isnull=True,
        ).values('id', 'status')

        payment_objs = []
        methods = [m[0] for m in Payment.PAYMENT_METHOD_CHOICES]
        for row in regs_without_payment_qs:
            reg_id = row['id']
            r_status = row['status']
            if r_status == 'cancelled':
                p_status = random.choices(['refunded', 'cancelled'], weights=[70, 30], k=1)[0]
            else:
                p_status = random.choices(['paid', 'pending', 'failed'], weights=[95, 3, 2], k=1)[0]
            # created_at을 기준 시각으로 먼저 생성
            created_at_ts = random_recent_datetime(90)
            paid_at = None
            canceled_at = None
            if p_status == 'paid':
                # created_at 이후 최대 72시간 내 결제 완료
                paid_at = min(timezone.now(), created_at_ts + timedelta(hours=random.randint(0, 72)))
            if p_status in ('cancelled', 'refunded'):
                if random.random() < 0.7:
                    # 결제 후 취소/환불: created_at 이후 결제 → 그 후 72시간 내 취소
                    paid_at = min(timezone.now(), created_at_ts + timedelta(hours=random.randint(0, 72)))
                    canceled_at = min(timezone.now(), paid_at + timedelta(hours=random.randint(0, 72)))
                else:
                    # 결제 없이 바로 취소/환불처럼 보이도록 created_at 이후 임의시간
                    canceled_at = min(timezone.now(), created_at_ts + timedelta(hours=random.randint(0, 72)))
            payment_objs.append(Payment(
                course_registration_id=reg_id,
                amount=random.randint(10_000, 200_000),
                payment_method=random.choice(methods),
                status=p_status,
                paid_at=paid_at,
                canceled_at=canceled_at,
                created_at=created_at_ts,
            ))
        payments_created = Payment.objects.bulk_create(
            payment_objs,
            ignore_conflicts=True,
            batch_size=batch_size,
        )
        total_payments_created += len(payments_created)
        if (start // batch_size) % 5 == 0:
            print(f"  진행 상황(CourseRegs/Payments): +{len(created)}/+{len(payments_created)} (누적 {total_regs_created}/{total_payments_created})")
    print(f"CourseRegistration 생성: {total_regs_created}개, Payment 생성: {total_payments_created}개")


def seed_test_registrations_and_payments(users_limit=50_000, registrations_per_user=1, batch_size=5_000):
    User = get_user_model()
    now = timezone.now()
    user_ids = list(User.objects.order_by('id').values_list('id', flat=True)[:users_limit])
    available_test_ids = list(
        Test.objects.filter(is_active=True, start_at__lte=now, end_at__gte=now)
        .order_by('id')
        .values_list('id', flat=True)
    )
    if not available_test_ids:
        print("TestRegistration 스킵: 사용 가능한 시험이 없습니다.")
        return
    test_meta = {
        row['id']: (row['start_at'], row['end_at'])
        for row in Test.objects.filter(id__in=available_test_ids).values('id', 'start_at', 'end_at')
    }
    reg_statuses = ['registered', 'in_progress', 'completed', 'cancelled']
    reg_weights = [60, 20, 15, 5]
    hot_size = max(1, min(len(available_test_ids), 800))
    warm_size = max(1, min(len(available_test_ids) - hot_size, 4000))
    hot_ids = available_test_ids[:hot_size]
    warm_ids = available_test_ids[hot_size:hot_size + warm_size]
    rest_ids = available_test_ids[hot_size + warm_size:]

    total_regs_created = 0
    total_payments_created = 0
    for start in range(0, len(user_ids), batch_size):
        batch_user_ids = user_ids[start:start + batch_size]
        reg_objs = []
        planned_pairs = []  # (user_id, test_id, status)
        for idx, user_id in enumerate(batch_user_ids, start=start):
            for j in range(registrations_per_user):
                bucket = random.choices(['hot', 'warm', 'rest'], weights=[70, 25, 5], k=1)[0]
                if bucket == 'hot' and hot_ids:
                    test_id = random.choice(hot_ids)
                elif bucket == 'warm' and warm_ids:
                    test_id = random.choice(warm_ids)
                elif rest_ids:
                    test_id = random.choice(rest_ids)
                else:
                    test_id = available_test_ids[(idx * 11 + j) % len(available_test_ids)]
                status = random.choices(reg_statuses, weights=reg_weights, k=1)[0]
                attempted_at = None
                if status == 'completed':
                    t_start, t_end = test_meta.get(test_id, (now, now))
                    end_bound = min(t_end, now)
                    if t_start < end_bound:
                        delta_sec = int((end_bound - t_start).total_seconds())
                        attempted_at = t_start + timedelta(seconds=random.randint(0, max(delta_sec, 1)))
                planned_pairs.append((user_id, test_id, status))
                reg_objs.append(TestRegistration(
                    user_id=user_id,
                    test_id=test_id,
                    status=status,
                    attempted_at=attempted_at,
                ))
        created = TestRegistration.objects.bulk_create(
            reg_objs,
            ignore_conflicts=True,
            batch_size=batch_size,
        )
        total_regs_created += len(created)

        pair_test_ids = [t for (_, t, _) in planned_pairs]
        regs_without_payment_qs = TestRegistration.objects.filter(
            user_id__in=batch_user_ids,
            test_id__in=set(pair_test_ids),
            payment__isnull=True,
        ).values('id', 'status')

        payment_objs = []
        methods = [m[0] for m in Payment.PAYMENT_METHOD_CHOICES]
        for row in regs_without_payment_qs:
            reg_id = row['id']
            r_status = row['status']
            if r_status == 'cancelled':
                p_status = random.choices(['refunded', 'cancelled'], weights=[70, 30], k=1)[0]
            else:
                p_status = random.choices(['paid', 'pending', 'failed'], weights=[95, 3, 2], k=1)[0]
            created_at_ts = random_recent_datetime(90)
            paid_at = None
            canceled_at = None
            if p_status == 'paid':
                paid_at = min(timezone.now(), created_at_ts + timedelta(hours=random.randint(0, 72)))
            if p_status in ('cancelled', 'refunded'):
                if random.random() < 0.7:
                    paid_at = min(timezone.now(), created_at_ts + timedelta(hours=random.randint(0, 72)))
                    canceled_at = min(timezone.now(), paid_at + timedelta(hours=random.randint(0, 72)))
                else:
                    canceled_at = min(timezone.now(), created_at_ts + timedelta(hours=random.randint(0, 72)))
            payment_objs.append(Payment(
                test_registration_id=reg_id,
                amount=random.randint(10_000, 200_000),
                payment_method=random.choice(methods),
                status=p_status,
                paid_at=paid_at,
                canceled_at=canceled_at,
                created_at=created_at_ts,
            ))
        payments_created = Payment.objects.bulk_create(
            payment_objs,
            ignore_conflicts=True,
            batch_size=batch_size,
        )
        total_payments_created += len(payments_created)
        if (start // batch_size) % 5 == 0:
            print(f"  진행 상황(TestRegs/Payments): +{len(created)}/+{len(payments_created)} (누적 {total_regs_created}/{total_payments_created})")
    print(f"TestRegistration 생성: {total_regs_created}개, Payment 생성: {total_payments_created}개")


def rebuild_course_registration_counts():
    with connection.cursor() as cursor:
        cursor.execute("UPDATE courses SET registrations_count = 0;")
        cursor.execute(
            """
            UPDATE courses c
            SET registrations_count = sub.cnt
            FROM (
                SELECT course_id, COUNT(*) AS cnt
                FROM course_registrations
                GROUP BY course_id
            ) sub
            WHERE c.id = sub.course_id;
            """
        )
    print("Course.registrations_count 재계산 완료")


def rebuild_test_registration_counts():
    with connection.cursor() as cursor:
        cursor.execute("UPDATE tests SET registrations_count = 0;")
        cursor.execute(
            """
            UPDATE tests t
            SET registrations_count = sub.cnt
            FROM (
                SELECT test_id, COUNT(*) AS cnt
                FROM test_registrations
                GROUP BY test_id
            ) sub
            WHERE t.id = sub.test_id;
            """
        )
    print("Test.registrations_count 재계산 완료")

def main():
    ensure_admin()
    seed_users(n=50_000)
    # 대량 데이터 생성: 수업 100만, 시험 100만
    seed_courses(n=1_000_000, batch_size=10_000)
    seed_tests(n=1_000_000, batch_size=10_000)
    # 등록 및 결제 생성: 사용자당 1개씩 예시
    seed_course_registrations_and_payments(users_limit=50_000, registrations_per_user=1)
    seed_test_registrations_and_payments(users_limit=50_000, registrations_per_user=1)
    # 카운터 재계산 (배치 생성은 post_save 신호가 발생하지 않음)
    rebuild_course_registration_counts()
    rebuild_test_registration_counts()
    print("더미 데이터 생성 완료.")

if __name__ == "__main__":
    main()