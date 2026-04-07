from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "title", "notification_type", "created_at", "read_at")
    list_filter = ("notification_type", "created_at", "read_at")
    search_fields = ("title", "message", "user__username", "user__first_name", "user__last_name")
    readonly_fields = ("created_at",)
