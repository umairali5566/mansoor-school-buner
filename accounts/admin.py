from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Student, Teacher, Classroom


class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Role Information", {"fields": ("role",)}),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Role Information", {"fields": ("role",)}),
    )


@admin.register(CustomUser)
class CustomUserRegisteredAdmin(CustomUserAdmin):
    pass


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "roll_number",
        "class_name",
        "admission_class",
        "admission_date",
        "parent_email",
    )
    list_filter = ("class_name", "admission_date", "admission_class")
    search_fields = ("full_name", "roll_number", "user__username", "user__first_name", "user__last_name")
    autocomplete_fields = ("admission_class",)

    def display_name(self, obj):
        return obj.display_name

    display_name.short_description = "Student Name"


class ClassroomAdmin(admin.ModelAdmin):
    list_display = ('name', 'teacher_count')
    search_fields = ('name',)

    def teacher_count(self, obj):
        return obj.teachers.count()
    teacher_count.short_description = 'Teachers'


class TeacherAdmin(admin.ModelAdmin):
    list_display = ('user', 'subject', 'assigned_classes', 'student_count', 'phone')
    filter_horizontal = ('classes',)

    def assigned_classes(self, obj):
        return ", ".join([cls.name for cls in obj.classes.all()])
    assigned_classes.short_description = 'Assigned Classes'

    def student_count(self, obj):
        # Count students in the teacher's classes
        class_names = list(obj.classes.values_list('name', flat=True))
        return Student.objects.filter(class_name__in=class_names).count()
    student_count.short_description = 'Students'


admin.site.register(Classroom, ClassroomAdmin)
admin.site.register(Teacher, TeacherAdmin)
