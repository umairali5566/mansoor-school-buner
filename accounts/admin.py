from django.contrib import admin
from django import forms
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


class ClassroomAdminForm(forms.ModelForm):
    teachers = forms.ModelMultipleChoiceField(
        queryset=Teacher.objects.select_related("user").order_by("user__username"),
        required=False,
        widget=admin.widgets.FilteredSelectMultiple("Teachers", is_stacked=False),
        help_text="Assign one or more teachers for this class.",
    )

    class Meta:
        model = Classroom
        fields = ["name", "teachers", "attendance_teacher"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["teachers"].initial = self.instance.teachers.all()

    def clean(self):
        cleaned_data = super().clean()
        teachers = cleaned_data.get("teachers")
        attendance_teacher = cleaned_data.get("attendance_teacher")
        if attendance_teacher and teachers is not None and attendance_teacher not in teachers:
            self.add_error(
                "attendance_teacher",
                "Attendance teacher must also be selected in assigned teachers.",
            )
        return cleaned_data

    def save(self, commit=True):
        classroom = super().save(commit=False)
        if commit:
            classroom.save()
            classroom.teachers.set(self.cleaned_data.get("teachers"))
        return classroom

    def save_m2m(self):
        super().save_m2m()
        if self.instance.pk:
            self.instance.teachers.set(self.cleaned_data.get("teachers"))


class ClassroomAdmin(admin.ModelAdmin):
    form = ClassroomAdminForm
    list_display = ("name", "teacher_count", "attendance_teacher_name")
    search_fields = ("name", "teachers__user__username", "teachers__user__first_name", "teachers__user__last_name")
    autocomplete_fields = ("attendance_teacher",)

    def teacher_count(self, obj):
        return obj.teachers.count()
    teacher_count.short_description = "Teachers"

    def attendance_teacher_name(self, obj):
        teacher = obj.attendance_teacher
        if teacher is None:
            return "-"
        return teacher.user.get_full_name() or teacher.user.username

    attendance_teacher_name.short_description = "Attendance Teacher"


class TeacherAdmin(admin.ModelAdmin):
    list_display = ("user", "subject", "assigned_classes", "attendance_classes", "student_count", "phone")
    filter_horizontal = ("classes",)
    search_fields = ("user__username", "user__first_name", "user__last_name", "subject", "phone")

    def assigned_classes(self, obj):
        return ", ".join([cls.name for cls in obj.classes.all()])
    assigned_classes.short_description = "Assigned Classes"

    def attendance_classes(self, obj):
        return ", ".join(obj.attendance_classes.order_by("name").values_list("name", flat=True)) or "-"

    attendance_classes.short_description = "Attendance Classes"

    def student_count(self, obj):
        # Count students in the teacher's classes
        class_names = list(obj.classes.values_list("name", flat=True))
        return Student.objects.filter(class_name__in=class_names).count()
    student_count.short_description = "Students"


admin.site.register(Classroom, ClassroomAdmin)
admin.site.register(Teacher, TeacherAdmin)
