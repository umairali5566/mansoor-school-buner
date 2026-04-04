"""
Accounts Views Module

This module handles all views related to user accounts including:
- Authentication (login/logout)
- Dashboards (admin, teacher, student)
- Student management (CRUD operations)
- Teacher management (CRUD operations)
- User profile management
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.hashers import make_password
from django.contrib.auth.forms import AuthenticationForm
from django.utils.crypto import get_random_string
from django.utils.timezone import localdate
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db.models import Count, Q
from datetime import date, timedelta
import json
import logging

from .models import CustomUser, Student, Teacher, Classroom
from .forms import (
    AdminStudentProfileEditForm,
    StudentCreateForm,
    TeacherCreateForm,
    DEFAULT_PASSWORD,
)
from attendance.models import Attendance, StudentFaceData
from results.models import Result
from homework.models import Homework


# =========================================================
# LOGGING
# =========================================================

LOGGER = logging.getLogger(__name__)


# =========================================================
# ROLE CHECK HELPERS
# =========================================================

def is_admin(user):
    """Check if user is an authenticated admin."""
    return user.is_authenticated and user.role == "ADMIN"


def is_teacher(user):
    """Check if user is an authenticated teacher."""
    return user.is_authenticated and user.role == "TEACHER"


def is_student(user):
    """Check if user is an authenticated student."""
    return user.is_authenticated and user.role == "STUDENT"


def is_teacher_or_admin(user):
    """Check if user is either admin or teacher."""
    return is_admin(user) or is_teacher(user)


def get_user_role(user):
    """Get the role of a user, returning empty string for unauthenticated."""
    return getattr(user, "role", "") or ""


def filter_attendance_for_classes(queryset, class_names):
    """Filter attendance queryset by allowed class names."""
    if not class_names:
        return queryset.none()
    return queryset.filter(
        Q(student_class__in=class_names)
        | Q(student_class="", student__class_name__in=class_names)
    )


# =========================================================
# AUTHENTICATION VIEWS
# =========================================================

def _get_redirect_url(user):
    """Get the appropriate redirect URL based on user role."""
    role_redirects = {
        "ADMIN": "admin_dashboard",
        "TEACHER": "teacher_dashboard",
        "STUDENT": "student_dashboard",
    }
    return role_redirects.get(get_user_role(user), "login")


def login_view(request):
    """Handle user login with role-based redirection."""
    if request.user.is_authenticated:
        return redirect(_get_redirect_url(request.user))

    form = AuthenticationForm(request, data=request.POST or None)
    for field in form.fields.values():
        field.widget.attrs.update({"class": "form-control"})

    if request.method == "POST":
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect(_get_redirect_url(user))
        messages.error(request, "Invalid username or password")

    return render(request, "accounts/login.html", {"form": form})


@require_POST
@login_required
def logout_view(request):
    """Handle user logout."""
    logout(request)
    return redirect("login")


# =========================================================
# DASHBOARD HELPERS
# =========================================================

def get_student_queryset():
    """Get optimized student queryset ordered by class and roll number."""
    return Student.objects.select_related("user", "admission_class").order_by(
        "class_name", "roll_number", "full_name"
    )


def get_attendance_stats(records_queryset, total_students):
    """Calculate attendance statistics from a filtered queryset."""
    marked_ids = records_queryset.values("student_id").distinct().count()
    return {
        "present_count": records_queryset.filter(status="Present").values("student_id").distinct().count(),
        "absent_count": records_queryset.filter(status="Absent").values("student_id").distinct().count(),
        "marked_count": marked_ids,
        "unmarked_count": max(total_students - marked_ids, 0),
    }


def get_teacher_class_names(teacher):
    """Get list of class names assigned to a teacher."""
    return list(teacher.classes.values_list("name", flat=True))


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    """Display admin dashboard with overall system statistics."""
    today = localdate()
    students_count = Student.objects.count()
    teachers_count = Teacher.objects.count()
    assigned_teachers_count = Teacher.objects.filter(classes__isnull=False).distinct().count()

    today_records = Attendance.objects.filter(date=today)
    today_stats = get_attendance_stats(today_records, students_count)

    all_time_present = Attendance.objects.filter(status="Present").count()
    all_time_absent = Attendance.objects.filter(status="Absent").count()

    # Today's attendance chart data
    today_chart_data = [
        today_stats["present_count"],
        today_stats["absent_count"],
        today_stats["unmarked_count"]
    ]

    # Weekly attendance data (last 7 days)
    weekly_labels = []
    weekly_present = []
    weekly_absent = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_records = Attendance.objects.filter(date=day)
        present_count = day_records.filter(status="Present").count()
        absent_count = day_records.filter(status="Absent").count()
        weekly_labels.append(day.strftime("%a"))
        weekly_present.append(present_count)
        weekly_absent.append(absent_count)

    # Class-wise attendance today
    class_labels = []
    class_present = []
    class_absent = []
    classes = Student.objects.values_list('class_name', flat=True).distinct()
    for cls in classes:
        if cls:
            class_labels.append(str(cls))
            present = Attendance.objects.filter(date=today, student__class_name=cls, status="Present").count()
            absent = Attendance.objects.filter(date=today, student__class_name=cls, status="Absent").count()
            class_present.append(present)
            class_absent.append(absent)

    context = {
        "students_count": students_count,
        "teachers_count": teachers_count,
        "assigned_teachers_count": assigned_teachers_count,
        "unassigned_teachers_count": teachers_count - assigned_teachers_count,
        "today_attendance": today_stats["marked_count"],
        "today_present_count": today_stats["present_count"],
        "today_absent_count": today_stats["absent_count"],
        "today_unmarked_count": today_stats["unmarked_count"],
        "present_count": all_time_present,
        "absent_count": all_time_absent,
        "today_chart_data": json.dumps(today_chart_data),
        "weekly_labels": json.dumps(weekly_labels),
        "weekly_present": json.dumps(weekly_present),
        "weekly_absent": json.dumps(weekly_absent),
        "class_labels": json.dumps(class_labels),
        "class_present": json.dumps(class_present),
        "class_absent": json.dumps(class_absent),
        "class_count": len(class_labels),
    }

    LOGGER.info(
        "Admin dashboard stats: date=%s students=%s attendance_today=%s present_today=%s absent_today=%s not_marked_today=%s",
        today, students_count, today_stats["marked_count"],
        today_stats["present_count"], today_stats["absent_count"], today_stats["unmarked_count"],
    )

    return render(request, "accounts/admin_dashboard.html", context)


# =========================================================
# TEACHER DASHBOARD
# =========================================================

@login_required
@user_passes_test(is_teacher)
def teacher_dashboard(request):
    """Display teacher dashboard with class-specific statistics and charts."""
    teacher = request.user.teacher
    class_names = get_teacher_class_names(teacher)

    if not class_names:
        return _render_teacher_dashboard_empty(request, class_names)

    today = localdate()
    students = Student.objects.filter(class_name__in=class_names)
    total_students = students.count()

    teacher_attendance = filter_attendance_for_classes(Attendance.objects.all(), class_names)
    today_records = teacher_attendance.filter(date=today)

    # Compute per-class student counts
    class_counts = {cls: students.filter(class_name=cls).count() for cls in class_names}

    today_stats = get_attendance_stats(today_records, total_students)
    today_present = today_stats["present_count"]
    today_absent = today_stats["absent_count"]
    total_attendance = teacher_attendance.count()

    # Recent attendance
    recent_attendance = (
        teacher_attendance.select_related("student")
        .order_by("-date", "-marked_at", "-id")[:5]
    )

    # Chart data
    today_chart_data = json.dumps([today_present, today_absent])

    # Weekly and monthly data
    weekly_labels, weekly_present, weekly_absent = _get_weekly_attendance(
        teacher_attendance, today
    )
    monthly_labels, monthly_present = _get_monthly_attendance(
        teacher_attendance, today
    )

    # Class-wise attendance
    class_labels, class_present, class_absent = _get_class_attendance(
        today_records, class_names
    )

    context = {
        "total_students": total_students,
        "today_present": today_present,
        "today_absent": today_absent,
        "total_attendance": total_attendance,
        "recent_attendance": recent_attendance,
        "today_chart_data": today_chart_data,
        "weekly_labels": json.dumps(weekly_labels),
        "weekly_present": json.dumps(weekly_present),
        "weekly_absent": json.dumps(weekly_absent),
        "monthly_labels": json.dumps(monthly_labels),
        "monthly_present": json.dumps(monthly_present),
        "class_labels": json.dumps(class_labels),
        "class_present": json.dumps(class_present),
        "class_absent": json.dumps(class_absent),
        "class_count": len(class_labels),
        "teacher_classes": class_names,
        "students": students,
        "class_counts": class_counts,
        "using_default_password": request.user.check_password(DEFAULT_PASSWORD),
    }

    # Add homework stats if homework app is available
    try:
        from homework.models import Homework
        from results.models import Result
        
        # Homework stats
        homework_qs = Homework.objects.filter(teacher=teacher)
        homework_total = homework_qs.count()
        homework_pending = homework_qs.filter(due_date__gte=today).count()
        homework_completed = homework_qs.filter(due_date__lt=today).count()
        
        # Recent homework
        recent_homework = homework_qs.order_by('-date_assigned')[:5]
        for hw in recent_homework:
            hw.is_overdue = hw.due_date < today if hw.due_date else False
        
        # Result stats
        result_total = Result.objects.filter(
            student__class_name__in=class_names
        ).count()
        
        context.update({
            "homework_stats": {
                "total": homework_total,
                "pending": homework_pending,
                "completed": homework_completed,
            },
            "recent_homework": recent_homework,
            "result_stats": {
                "total": result_total,
            },
        })
    except ImportError:
        pass

    LOGGER.info(
        "Teacher dashboard stats: user_id=%s classes=%s date=%s students=%s present=%s absent=%s total_attendance=%s",
        request.user.id, ",".join(class_names), today, total_students,
        today_present, today_absent, total_attendance,
    )

    return render(request, "accounts/teacher_dashboard.html", context)


def _render_teacher_dashboard_empty(request, class_names):
    """Render teacher dashboard with empty state when no classes assigned."""
    messages.warning(request, "You don't have a class assigned. Please contact the admin.")
    default_data = {
        "total_students": 0, "today_present": 0, "today_absent": 0,
        "total_attendance": 0, "recent_attendance": [],
        "today_chart_data": json.dumps([0, 0]),
        "weekly_labels": json.dumps([]), "weekly_present": json.dumps([]),
        "weekly_absent": json.dumps([]), "monthly_labels": json.dumps([]),
        "monthly_present": json.dumps([]), "class_labels": json.dumps([]),
        "class_present": json.dumps([]), "class_absent": json.dumps([]),
        "class_count": 0, "teacher_classes": class_names, "students": [],
        "class_counts": {}, "homework_stats": {"total": 0, "pending": 0, "completed": 0},
        "result_stats": {"total": 0},
        "using_default_password": request.user.check_password(DEFAULT_PASSWORD),
    }
    return render(request, "accounts/teacher_dashboard.html", default_data)


@login_required
@user_passes_test(is_teacher)
def teacher_classes(request):
    """Display classes assigned to the current teacher."""
    teacher = request.user.teacher
    class_names = get_teacher_class_names(teacher)
    
    # Get students in each class
    classes_data = []
    for class_name in class_names:
        students = Student.objects.filter(class_name=class_name)
        classes_data.append({
            'name': class_name,
            'student_count': students.count(),
            'students': students,
        })
    
    context = {
        'classes_data': classes_data,
        'teacher_classes': class_names,
    }
    return render(request, "accounts/teacher_classes.html", context)


def _get_weekly_attendance(attendance_qs, today):
    """Get weekly attendance data for charts."""
    labels, present, absent = [], [], []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        labels.append(day.strftime("%b %d"))
        day_records = attendance_qs.filter(date=day)
        present.append(day_records.filter(status="Present").count())
        absent.append(day_records.filter(status="Absent").count())
    return labels, present, absent


def _get_monthly_attendance(attendance_qs, today):
    """Get monthly attendance data for charts."""
    labels, present = [], []
    for i in range(29, -1, -1):
        day = today - timedelta(days=i)
        labels.append(day.strftime("%b %d"))
        present.append(attendance_qs.filter(date=day, status="Present").count())
    return labels, present


def _get_class_attendance(today_records, class_names):
    """Get class-wise attendance breakdown."""
    class_attendance = (
        today_records.values("student_class", "student__class_name", "status")
        .annotate(total=Count("id"))
    )

    classes = {}
    for record in class_attendance:
        cls = record["student_class"] or record["student__class_name"] or "-"
        status = record["status"]
        total = record["total"]
        if cls not in classes:
            classes[cls] = {"Present": 0, "Absent": 0}
        classes[cls][status] = total

    labels = list(classes.keys())
    return labels, [classes[c]["Present"] for c in labels], [classes[c]["Absent"] for c in labels]


# =========================================================
# STUDENT DASHBOARD
# =========================================================

@login_required
@user_passes_test(is_student)
def student_dashboard(request):
    """Display student dashboard with personal statistics."""
    user = request.user
    student = Student.objects.filter(user=user).first()

    if not student:
        messages.error(request, "Student profile not found.")
        return redirect("login")

    today = localdate()
    face = StudentFaceData.objects.filter(student=student).first()
    attendance_qs = Attendance.objects.filter(student=student).order_by("-date", "-marked_at", "-id")
    attendance_count = attendance_qs.count()
    present_count = attendance_qs.filter(status="Present").count()
    attendance_percentage = round((present_count / attendance_count) * 100, 1) if attendance_count else 0
    attendance_stroke_offset = 326.73 - (attendance_percentage / 100) * 326.73

    results_qs = Result.objects.filter(student=student).order_by("-date", "-id")
    results_count = results_qs.count()
    recent_results = list(results_qs[:5])
    for result in recent_results:
        total_marks = result.total_marks or 0
        percentage = (result.marks / total_marks) * 100 if total_marks > 0 else 0
        result.marks_obtained = result.marks
        result.percentage = round(percentage, 1)
        if percentage >= 80:
            result.grade = "A"
        elif percentage >= 70:
            result.grade = "B"
        elif percentage >= 60:
            result.grade = "C"
        elif percentage >= 50:
            result.grade = "D"
        elif percentage >= 40:
            result.grade = "E"
        else:
            result.grade = "F"

    homeworks = Homework.objects.select_related("teacher__user").filter(
        class_name=student.class_name
    ).order_by("-date_assigned")
    recent_homework = list(homeworks[:5])
    for hw in recent_homework:
        teacher_name = "-"
        if hw.teacher and hw.teacher.user:
            teacher_name = hw.teacher.user.get_full_name() or hw.teacher.user.username
        hw.teacher_name = teacher_name
        hw.is_overdue = bool(hw.due_date and hw.due_date < today)

    recent_attendance = list(attendance_qs[:7])
    weekly_labels = []
    weekly_attendance = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        weekly_labels.append(day.strftime("%a"))
        day_record = attendance_qs.filter(date=day).first()
        weekly_attendance.append(1 if day_record and day_record.status == "Present" else 0)

    return render(request, "accounts/student_dashboard.html", {
        "student": student,
        "face": face,
        "attendance_count": attendance_count,
        "attendance_percentage": attendance_percentage,
        "attendance_stroke_offset": round(attendance_stroke_offset, 2),
        "results_count": results_count,
        "attendance": attendance_count,
        "results": results_count,
        "homework": homeworks.count(),
        "homeworks": homeworks,
        "recent_homework": recent_homework,
        "recent_results": recent_results,
        "recent_attendance": recent_attendance,
        "weekly_labels": json.dumps(weekly_labels),
        "weekly_attendance": json.dumps(weekly_attendance),
        "homework_count": homeworks.count(),
        "using_default_password": request.user.check_password(DEFAULT_PASSWORD),
    })


# =========================================================
# STUDENT ADMISSION HELPERS
# =========================================================

def user_can_view_student(user, student):
    """Check if user has permission to view a student's profile."""
    if not user.is_authenticated:
        return False
    role = get_user_role(user)
    if role == "ADMIN" or getattr(user, "is_superuser", False):
        return True
    if role == "STUDENT":
        return getattr(user, "student", None) and user.student.id == student.id
    if role == "TEACHER":
        teacher = getattr(user, "teacher", None)
        return teacher is not None and teacher.classes.filter(name=student.class_name).exists()
    return False


def render_student_admission_form(request, student=None, form_class=StudentCreateForm):
    """Render student admission form for create/edit operations."""
    if request.method == "POST":
        form = form_class(request.POST, student=student)
        if form.is_valid():
            student_record = form.save()
            messages.success(
                request,
                "Admission saved successfully." if student is None else "Admission details updated successfully.",
            )
            if student is None:
                return render(
                    request,
                    "accounts/student_created.html",
                    {
                        "username": form.generated_username,
                        "password": form.generated_password,
                        "student": student_record,
                    },
                )
            return redirect("student_admissions")
    else:
        form = form_class(student=student)

    classrooms = Classroom.objects.order_by("name")
    return render(
        request,
        "accounts/student_admission_form.html",
        {
            "form": form,
            "student": student,
            "classrooms": classrooms,
            "page_title": "Add Student Admission" if student is None else "Edit Student Admission",
            "page_eyebrow": "Admission workflow",
            "submit_label": "Create Admission" if student is None else "Save Admission Changes",
            "cancel_url": "student_admissions" if student is None else "student_profile",
        },
    )


# =========================================================
# STUDENT MANAGEMENT VIEWS
# =========================================================

@login_required
@user_passes_test(is_admin)
def student_admissions(request):
    """List all student admissions with filtering and pagination."""
    search_query = (request.GET.get("q") or "").strip()
    selected_class_id = (request.GET.get("class_id") or "").strip()
    selected_date_raw = (request.GET.get("admission_date") or "").strip()

    classrooms = Classroom.objects.order_by("name")
    base_queryset = get_student_queryset()
    students = base_queryset.order_by("-admission_date", "full_name", "roll_number")

    # Apply filters
    if search_query:
        students = students.filter(
            Q(full_name__icontains=search_query)
            | Q(user__first_name__icontains=search_query)
            | Q(user__last_name__icontains=search_query)
            | Q(user__username__icontains=search_query)
            | Q(roll_number__icontains=search_query)
        )

    if selected_class_id:
        selected_classroom = classrooms.filter(id=selected_class_id).first()
        if selected_classroom:
            students = students.filter(
                Q(class_name=selected_classroom.name) | Q(admission_class=selected_classroom)
            )

    selected_date = None
    if selected_date_raw:
        try:
            selected_date = date.fromisoformat(selected_date_raw)
            students = students.filter(admission_date=selected_date)
        except ValueError:
            messages.warning(request, "The admission date filter was invalid and has been ignored.")

    paginator = Paginator(students, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    current_month_start = localdate().replace(day=1)
    return render(request, "accounts/student_admissions.html", {
        "page_obj": page_obj,
        "students": page_obj.object_list,
        "classrooms": classrooms,
        "search_query": search_query,
        "selected_class_id": selected_class_id,
        "selected_admission_date": selected_date_raw,
        "total_admissions": base_queryset.count(),
        "filtered_count": students.count(),
        "this_month_count": base_queryset.filter(admission_date__gte=current_month_start).count(),
    })


@login_required
@user_passes_test(is_admin)
def student_list(request):
    """List all students (simple view)."""
    return render(request, "accounts/student_list.html", {
        "students": get_student_queryset()
    })


@login_required
@user_passes_test(is_admin)
def add_student(request):
    """Render student creation form."""
    return render_student_admission_form(request)


@login_required
@user_passes_test(is_admin)
def edit_student(request, student_id):
    """Render student edit form."""
    student = get_object_or_404(get_student_queryset(), id=student_id)
    return render_student_admission_form(request, student=student, form_class=AdminStudentProfileEditForm)


@login_required
@user_passes_test(is_admin)
def delete_student(request, student_id):
    """Delete a student and associated user account."""
    student = get_object_or_404(Student.objects.select_related("user"), id=student_id)
    student.user.delete()
    messages.success(request, "Student deleted successfully.")
    return redirect("student_admissions")


# =========================================================
# TEACHER MANAGEMENT VIEWS
# =========================================================

@login_required
@user_passes_test(is_admin)
def teacher_list(request):
    """List all teachers."""
    return render(request, "accounts/teacher_list.html", {
        "teachers": Teacher.objects.select_related("user").prefetch_related("classes").all()
    })


@login_required
@user_passes_test(is_admin)
def assign_teacher_classes(request, teacher_id):
    """Assign or unassign classes to a teacher."""
    teacher = get_object_or_404(Teacher, id=teacher_id)
    classrooms = Classroom.objects.order_by("name")

    if request.method == "POST":
        selected_class_ids = request.POST.getlist("class_ids")
        teacher.classes.set(classrooms.filter(id__in=selected_class_ids))
        messages.success(
            request,
            f"Classes assigned to {teacher.user.username} successfully." if selected_class_ids
            else f"All classes removed for {teacher.user.username}."
        )
        return redirect("teacher_list")

    return render(request, "accounts/assign_teacher_classes.html", {
        "teacher": teacher,
        "classrooms": classrooms,
        "assigned_ids": list(teacher.classes.values_list("id", flat=True)),
    })


@login_required
@user_passes_test(is_admin)
def add_teacher(request):
    """Create a new teacher account."""
    if request.method == "POST":
        form = TeacherCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            return render(request, "accounts/teacher_created.html", {
                "username": user.username,
                "password": form.generated_password
            })
        messages.error(request, " ".join(f"{field}: {', '.join(errors)}" for field, errors in form.errors.items()))
    else:
        form = TeacherCreateForm()
    return render(request, "accounts/add_teacher.html", {"form": form})


@login_required
@user_passes_test(is_admin)
def edit_teacher(request, teacher_id):
    """Edit teacher profile."""
    teacher = get_object_or_404(Teacher, id=teacher_id)

    if request.method == "POST":
        subject = request.POST.get("subject", "").strip()
        phone = request.POST.get("phone", "").strip()
        username = "".join(phone.split())

        if not username:
            messages.error(request, "Phone number is required.")
            return render(request, "accounts/edit_teacher.html", {"teacher": teacher})

        if CustomUser.objects.filter(username=username).exclude(id=teacher.user.id).exists():
            messages.error(request, "Another account already uses this phone number.")
            return render(request, "accounts/edit_teacher.html", {"teacher": teacher})

        teacher.user.username = username
        teacher.subject = subject
        teacher.phone = phone
        teacher.user.save()
        teacher.save()
        return redirect("teacher_list")

    return render(request, "accounts/edit_teacher.html", {"teacher": teacher})


@login_required
@user_passes_test(is_admin)
def delete_teacher(request, teacher_id):
    """Delete a teacher and associated user account."""
    teacher = get_object_or_404(Teacher, id=teacher_id)
    teacher.user.delete()
    return redirect("teacher_list")


# =========================================================
# PASSWORD RESET VIEWS
# =========================================================

def reset_user_password(request, user_model, user_id, template_name):
    """Generic password reset helper for any user type."""
    user = get_object_or_404(user_model.objects.select_related("user"), id=user_id)
    new_password = get_random_string(8)
    user.user.password = make_password(new_password)
    user.user.save()
    return render(request, template_name, {
        "username": user.user.username,
        "password": new_password
    })


@login_required
@user_passes_test(is_admin)
def reset_student_password(request, student_id):
    """Reset a student's password."""
    return reset_user_password(request, Student, student_id, "accounts/password_reset_done.html")


@login_required
@user_passes_test(is_admin)
def reset_teacher_password(request, teacher_id):
    """Reset a teacher's password."""
    return reset_user_password(request, Teacher, teacher_id, "accounts/password_reset_done.html")


# =========================================================
# PROFILE VIEWS
# =========================================================

@login_required
def student_profile(request, id):
    """Display student profile with attendance summary."""
    student = get_object_or_404(
        Student.objects.select_related("user", "admission_class"),
        id=id,
    )

    if not user_can_view_student(request.user, student):
        messages.error(request, "You are not allowed to view this student profile.")
        return redirect(_get_redirect_url(request.user))

    attendances = Attendance.objects.filter(student=student).order_by("-date", "-marked_at")
    present_count = attendances.filter(status="Present").count()
    absent_count = attendances.filter(status="Absent").count()
    total = present_count + absent_count
    percentage = (present_count / total * 100) if total > 0 else 0

    return render(request, "accounts/student_profile.html", {
        "student": student,
        "attendances": attendances,
        "present_count": present_count,
        "absent_count": absent_count,
        "percentage": round(percentage, 2),
        "can_edit_admission": is_admin(request.user),
        "show_parent_contact": get_user_role(request.user) != "TEACHER",
    })


@login_required
@user_passes_test(is_admin)
def edit_student_profile(request, student_id):
    """Edit student admission details."""
    student = get_object_or_404(get_student_queryset(), id=student_id)
    return render_student_admission_form(request, student=student, form_class=AdminStudentProfileEditForm)


@login_required
@user_passes_test(is_teacher)
def teacher_add_student(request):
    """Redirect teachers - they cannot add students."""
    messages.info(
        request,
        "Student admissions are managed by administrators. Teachers can review students in their assigned classes from the dashboard.",
    )
    return redirect("teacher_dashboard")


# =========================================================
# VIEW STUDENTS
# =========================================================
@login_required
@user_passes_test(is_teacher_or_admin)
def view_students(request):
    students = Student.objects.select_related("user")
    if is_teacher(request.user):
        class_names = get_teacher_class_names(request.user.teacher)
        students = students.filter(class_name__in=class_names)

    context = {
        'students': students,
    }
    return render(request, 'accounts/view_students.html', context)
