from django.contrib import admin
from tests.models import Test, TestRegistration

@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "is_active", "start_at", "end_at", "registrations_count", "created_at", "updated_at")
    search_fields = ("title",)
    list_filter = ("is_active",)
    ordering = ("-created_at",)

@admin.register(TestRegistration)
class TestRegistrationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "test", "status", "attempted_at", "created_at")
    list_filter = ("status",)
    search_fields = ("user__email", "test__title")
    ordering = ("-created_at",)
# Register your models here.
