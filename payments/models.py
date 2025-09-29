from django.db import models
from django.utils import timezone


class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ("card", "card"),
        ("kakaopay", "kakaopay"),
        ("naverpay", "naverpay"),
        ("tosspay", "tosspay"),
        ("bank_transfer", "bank_transfer"),
    ]

    STATUS_CHOICES = [
        ("pending", "pending"),
        ("paid", "paid"),
        ("cancelled", "cancelled"),
        ("failed", "failed"),
        ("refunded", "refunded"),
    ]

    course_registration = models.OneToOneField(
        "courses.CourseRegistration",
        on_delete=models.CASCADE,
        related_name="payment",
        null=True,
        blank=True,
    )
    test_registration = models.OneToOneField(
        "tests.TestRegistration",
        on_delete=models.CASCADE,
        related_name="payment",
        null=True,
        blank=True,
    )

    amount = models.PositiveIntegerField()
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="paid")

    paid_at = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payments"
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["paid_at"], name="payments_paid_at_idx", condition=models.Q(status="paid")),
            models.Index(fields=["canceled_at"], name="payments_canceled_at_idx", condition=models.Q(status__in=["cancelled", "refunded"]))
        ]
        constraints = [
            # 대상은 반드시 하나만 설정 (XOR)
            models.CheckConstraint(
                check=(
                    (models.Q(course_registration__isnull=False) & models.Q(test_registration__isnull=True)) |
                    (models.Q(course_registration__isnull=True) & models.Q(test_registration__isnull=False))
                ),
                name="payment_exactly_one_target",
            ),
            # 금액은 양수
            models.CheckConstraint(
                check=models.Q(amount__gt=0),
                name="payment_amount_gt_0",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.status == "paid" and self.paid_at is None:
            self.paid_at = timezone.now()
        if self.status in {"cancelled", "refunded"} and self.canceled_at is None:
            self.canceled_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        target = "course" if self.course_registration_id else "test"
        target_id = self.course_registration_id or self.test_registration_id
        return f"Payment<{self.id}> {target}:{target_id} {self.amount}KRW {self.status}"
