from django.contrib import admin
from .models import User

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "email", "is_active", "is_staff", "is_superuser", "last_login", "created_at", "updated_at")
    search_fields = ("email",)
    list_filter = ("is_active", "is_staff", "is_superuser")
    readonly_fields = ("password", "last_login", "created_at", "updated_at")
    ordering = ("-id",)