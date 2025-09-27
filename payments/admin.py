from django.contrib import admin
from payments.models import Payment

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "amount",
        "payment_method",
        "status",
        "course_registration",
        "test_registration",
        "paid_at",
        "canceled_at",
        "created_at",
    )
    list_filter = ("status", "payment_method")
    search_fields = (
        "course_registration__user__email",
        "course_registration__course__title",
        "test_registration__user__email",
        "test_registration__test__title",
    )
    ordering = ("-created_at",)