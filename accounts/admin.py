from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Student
from .models import Teacher


class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Role Information", {"fields": ("role",)}),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Role Information", {"fields": ("role",)}),
    )


admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Student)
admin.site.register(Teacher)