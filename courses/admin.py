from django.contrib import admin
from courses.models import Course, CourseRegistration

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "is_active", "start_at", "end_at", "registrations_count", "created_at", "updated_at")
    search_fields = ("title",)
    list_filter = ("is_active",)
    ordering = ("-created_at",)

@admin.register(CourseRegistration)
class CourseRegistrationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "course", "status", "attempted_at", "created_at")
    list_filter = ("status",)
    search_fields = ("user__email", "course__title")
    ordering = ("-created_at",)