from django.contrib import admin
from .models import Attendance


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "student_class",
        "date",
        "status",
        "marked_by",
        "marked_by_teacher",
        "marked_at",
    )
    list_filter = ("date", "status", "marked_by")
    search_fields = ("student__full_name", "student__user__username", "student_class")


from .models import ClassroomCamera

admin.site.register(ClassroomCamera)
