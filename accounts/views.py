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
from django.http import JsonResponse
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.hashers import make_password
from django.contrib.auth.forms import AuthenticationForm
from django.conf import settings
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils import timezone
from django.utils.timezone import localdate
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q, Count
from datetime import date
import logging

from .models import CustomUser, Student, Teacher, Classroom
from .forms import (
    AdminStudentProfileEditForm,
    AdminStudentProfileForm,
    StudentCreateForm,
    StudentProfileForm,
    TeacherCreateForm,
    DEFAULT_PASSWORD,
)
from attendance.models import Attendance
from results.models import Result
from homework.models import Homework, Assignment, AssignmentSubmission, Quiz, StudentQuizAttempt


# =========================================================
# LOGGING
# =========================================================

LOGGER = logging.getLogger(__name__)


# =========================================================
# HOMEPAGE
# =========================================================

def home(request):
    """Root entrypoint. No public marketing page; route users to login/dashboard."""
    if request.user.is_authenticated:
        if request.user.role == 'ADMIN':
            return redirect('admin_dashboard')
        elif request.user.role == 'TEACHER':
            return redirect('teacher_dashboard')
        else:
            return redirect('student_dashboard')
    return redirect("login")


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
    """Return role-based dashboard URL."""
    if user.is_superuser:
        return "/admin-dashboard/"
    if getattr(user, "role", "") == "TEACHER":
        return "/teacher-dashboard/"
    if getattr(user, "role", "") == "STUDENT":
        return "/student-dashboard/"
    return "/"


def _reset_login_attempts(request):
    request.session.pop("auth_login_attempts", None)


def _login_attempt_state(request):
    """
    Session-backed login throttle state:
    {
        "count": int,
        "first_attempt_ts": epoch_seconds
    }
    """
    state = request.session.get("auth_login_attempts") or {}
    return {
        "count": int(state.get("count") or 0),
        "first_attempt_ts": int(state.get("first_attempt_ts") or 0),
    }


def _is_login_locked(request):
    max_attempts = max(int(getattr(settings, "LOGIN_THROTTLE_MAX_ATTEMPTS", 5)), 1)
    window_seconds = max(int(getattr(settings, "LOGIN_THROTTLE_WINDOW_SECONDS", 600)), 60)
    now_ts = int(timezone.now().timestamp())
    state = _login_attempt_state(request)

    if state["count"] <= 0 or state["first_attempt_ts"] <= 0:
        return False, 0

    elapsed = now_ts - state["first_attempt_ts"]
    if elapsed >= window_seconds:
        _reset_login_attempts(request)
        return False, 0

    if state["count"] >= max_attempts:
        return True, window_seconds - elapsed
    return False, 0


def _register_login_failure(request):
    window_seconds = max(int(getattr(settings, "LOGIN_THROTTLE_WINDOW_SECONDS", 600)), 60)
    now_ts = int(timezone.now().timestamp())
    state = _login_attempt_state(request)
    first_ts = state["first_attempt_ts"] or now_ts

    if now_ts - first_ts >= window_seconds:
        state = {"count": 0, "first_attempt_ts": now_ts}

    state["count"] += 1
    if not state["first_attempt_ts"]:
        state["first_attempt_ts"] = now_ts

    request.session["auth_login_attempts"] = state


def login_view(request):
    if request.user.is_authenticated:
        return redirect(_get_redirect_url(request.user))

    next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()
    error = None
    username = ""

    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()

        locked, retry_after = _is_login_locked(request)
        if locked:
            retry_minutes = max(1, (retry_after + 59) // 60)
            error = f"Too many login attempts. Please try again in {retry_minutes} minute(s)."
        else:
            form = AuthenticationForm(request, data=request.POST)
            if form.is_valid():
                user = form.get_user()
                login(request, user)
                _reset_login_attempts(request)

                if next_url and url_has_allowed_host_and_scheme(
                    url=next_url,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure(),
                ):
                    return redirect(next_url)

                return redirect(_get_redirect_url(user))

            _register_login_failure(request)
            error = "Invalid username or password."

    return render(
        request,
        "accounts/login.html",
        {
            "error": error,
            "next": next_url,
            "username": username,
        },
    )

@require_POST
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


def resolve_attendance_health(attendance_percentage):
    """Map attendance percentage to a friendly status + badge style."""
    if attendance_percentage > 75:
        return "Good", "status-badge-success"
    if attendance_percentage >= 50:
        return "Average", "status-badge-warning"
    return "Low", "status-badge-danger"


def build_overall_attendance_rows(students_queryset):
    """
    Build per-student overall attendance analytics without date filters.
    Returns sorted rows ready for dashboard tables.
    """
    students_with_totals = (
        students_queryset.select_related("user")
        .annotate(
            total_classes=Count("attendance"),
            total_present=Count("attendance", filter=Q(attendance__status="Present")),
        )
        .order_by("class_name", "roll_number", "user__username")
    )

    rows = []
    for student in students_with_totals:
        total_classes = int(getattr(student, "total_classes", 0) or 0)
        present_count = int(getattr(student, "total_present", 0) or 0)
        absent_count = max(total_classes - present_count, 0)
        overall_percentage = round((present_count / total_classes) * 100, 1) if total_classes else 0.0
        status_label, status_class = resolve_attendance_health(overall_percentage)
        rows.append(
            {
                "student_id": student.id,
                "student_name": student.display_name,
                "class_name": student.class_name or "-",
                "total_classes": total_classes,
                "present_count": present_count,
                "absent_count": absent_count,
                "overall_percentage": overall_percentage,
                "status_label": status_label,
                "status_class": status_class,
            }
        )

    rows.sort(key=lambda item: (item["overall_percentage"], item["student_name"].lower()), reverse=True)
    return rows


def summarize_overall_attendance(rows):
    """Create summary metrics from overall attendance rows."""
    total_classes = sum(item["total_classes"] for item in rows)
    total_present = sum(item["present_count"] for item in rows)
    students_with_records = sum(1 for item in rows if item["total_classes"] > 0)
    overall_percentage = round((total_present / total_classes) * 100, 1) if total_classes else 0.0

    return {
        "overall_percentage": overall_percentage,
        "students_with_records": students_with_records,
        "good_count": sum(1 for item in rows if item["status_label"] == "Good"),
        "average_count": sum(1 for item in rows if item["status_label"] == "Average"),
        "low_count": sum(1 for item in rows if item["status_label"] == "Low"),
    }


def get_teacher_class_names(teacher):
    """Get list of class names assigned to a teacher."""
    return list(teacher.classes.values_list("name", flat=True))


def _teacher_display_name(teacher):
    if teacher is None:
        return "-"
    return (teacher.user.get_full_name() or teacher.user.username).strip()


def get_teacher_class_roles(teacher):
    """
    Build role-aware class metadata for teacher-facing screens.
    A teacher can be assigned to many classes, while only attendance teacher can mark attendance.
    """
    classes = teacher.classes.select_related("attendance_teacher__user").order_by("name")
    class_roles = []
    for classroom in classes:
        is_attendance_teacher = classroom.attendance_teacher_id == teacher.id
        class_roles.append(
            {
                "id": classroom.id,
                "name": classroom.name,
                "is_attendance_teacher": is_attendance_teacher,
                "role_label": "Attendance Teacher" if is_attendance_teacher else "Subject Teacher",
                "attendance_teacher_name": _teacher_display_name(classroom.attendance_teacher),
            }
        )
    return class_roles


def get_teacher_profile(user):
    """Safely fetch teacher profile; returns None if missing."""
    return Teacher.objects.select_related("user").prefetch_related(
        "classes__attendance_teacher__user",
        "attendance_classes__attendance_teacher__user",
    ).filter(user=user).first()


def get_student_profile(user):
    """Safely fetch student profile; returns None if missing."""
    return Student.objects.select_related("user").filter(user=user).first()


def get_dashboard_header(role):
    header_map = {
        "ADMIN": {
            "eyebrow": "Operations Center",
            "title": "Operations Dashboard",
            "subtitle": "Comprehensive school management with real-time monitoring, admissions, staff, and attendance tracking.",
            "badge_icon": "bi bi-shield-check",
            "badge_label": "Operations Center",
        },
        "TEACHER": {
            "eyebrow": "Teacher Workspace",
            "title": "Teacher Dashboard",
            "subtitle": "Plan classes, track attendance, and manage learning tasks from one dashboard.",
            "badge_icon": "bi bi-mortarboard-fill",
            "badge_label": "Teacher Workspace",
        },
        "STUDENT": {
            "eyebrow": "Student Portal",
            "title": "Learning Dashboard",
            "subtitle": "Track your academic progress, attendance, homework, and results in one place.",
            "badge_icon": "bi bi-person-fill",
            "badge_label": "Student Workspace",
        },
    }
    return header_map.get(role, {"eyebrow": "Workspace", "title": "Dashboard", "subtitle": ""})


def get_dashboard_topbar_actions(role, *, student_id=None):
    if role == "ADMIN":
        return [
            {
                "href": reverse("student_admissions"),
                "label": "Enrollment",
                "icon": "bi bi-journal-richtext",
                "variant": "btn btn-outline-light btn-sm",
            },
            {
                "href": reverse("live_attendance"),
                "label": "Live Attendance",
                "icon": "bi bi-camera-video-fill",
                "variant": "btn btn-light btn-sm",
            },
        ]

    if role == "TEACHER":
        return [
            {
                "href": reverse("mark_attendance"),
                "label": "Attendance",
                "icon": "bi bi-clipboard-check-fill",
                "variant": "btn btn-outline-light btn-sm",
            },
            {
                "href": reverse("upload_homework"),
                "label": "Upload Homework",
                "icon": "bi bi-cloud-arrow-up-fill",
                "variant": "btn btn-light btn-sm",
            },
        ]

    if role == "STUDENT":
        actions = [
            {
                "href": reverse("student_attendance"),
                "label": "My Attendance",
                "icon": "bi bi-calendar-check-fill",
                "variant": "btn btn-light btn-sm",
            },
        ]
        if student_id:
            actions.insert(
                0,
                {
                    "href": reverse("student_profile", kwargs={"id": student_id}),
                    "label": "My Profile",
                    "icon": "bi bi-person-circle",
                    "variant": "btn btn-outline-light btn-sm",
                },
            )
        return actions

    return []


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

    recent_attendance = (
        Attendance.objects.select_related("student__user")
        .order_by("-date", "-marked_at", "-id")[:6]
    )
    total_homework = Homework.objects.count()
    total_assignments = Assignment.objects.count()
    total_quizzes = Quiz.objects.count()
    total_submissions = AssignmentSubmission.objects.count()
    total_results = Result.objects.count()

    teacher_profiles = Teacher.objects.select_related("user").prefetch_related("classes").all()
    homework_counts = {
        row["teacher_id"]: row["count"]
        for row in Homework.objects.filter(teacher__isnull=False).values("teacher_id").annotate(count=Count("id"))
    }
    assignment_counts = {
        row["teacher_id"]: row["count"]
        for row in Assignment.objects.filter(teacher__isnull=False).values("teacher_id").annotate(count=Count("id"))
    }
    quiz_counts = {
        row["teacher_id"]: row["count"]
        for row in Quiz.objects.filter(teacher__isnull=False).values("teacher_id").annotate(count=Count("id"))
    }
    submission_counts = {
        row["assignment__teacher_id"]: row["count"]
        for row in AssignmentSubmission.objects.filter(assignment__teacher__isnull=False)
        .values("assignment__teacher_id")
        .annotate(count=Count("id"))
    }
    result_counts = {
        row["teacher_id"]: row["count"]
        for row in Result.objects.filter(teacher__isnull=False).values("teacher_id").annotate(count=Count("id"))
    }

    class_student_counts = {
        row["class_name"]: row["count"]
        for row in Student.objects.values("class_name").annotate(count=Count("id"))
    }
    pending_submission_counts = {}
    total_pending_submissions = 0
    assignment_with_submission_counts = Assignment.objects.select_related("class_assigned").annotate(
        submission_count=Count("submissions")
    )
    for assignment in assignment_with_submission_counts:
        class_name = assignment.class_assigned.name
        class_total_students = class_student_counts.get(class_name, 0)
        pending_count = max(class_total_students - assignment.submission_count, 0)
        if assignment.teacher_id:
            pending_submission_counts[assignment.teacher_id] = (
                pending_submission_counts.get(assignment.teacher_id, 0) + pending_count
            )
        total_pending_submissions += pending_count

    percentage_sum_by_teacher = {}
    percentage_count_by_teacher = {}
    for attempt in StudentQuizAttempt.objects.select_related("quiz").filter(quiz__teacher__isnull=False):
        max_score = attempt.quiz.total_marks if attempt.quiz.total_marks > 0 else 0
        if max_score <= 0:
            continue
        teacher_id = attempt.quiz.teacher_id
        percentage = (attempt.score / max_score) * 100
        percentage_sum_by_teacher[teacher_id] = percentage_sum_by_teacher.get(teacher_id, 0) + percentage
        percentage_count_by_teacher[teacher_id] = percentage_count_by_teacher.get(teacher_id, 0) + 1

    teacher_activity_rows = []
    active_teachers_with_activity = 0
    for teacher_profile in teacher_profiles:
        teacher_user_id = teacher_profile.user_id
        assignment_count = assignment_counts.get(teacher_user_id, 0)
        quiz_count = quiz_counts.get(teacher_user_id, 0)
        submission_count = submission_counts.get(teacher_user_id, 0)
        homework_count = homework_counts.get(teacher_profile.id, 0)
        result_count = result_counts.get(teacher_profile.id, 0)
        pending_count = pending_submission_counts.get(teacher_user_id, 0)
        total_uploads = homework_count + assignment_count + quiz_count + result_count
        class_names = ", ".join(sorted(teacher_profile.classes.values_list("name", flat=True))) or "-"
        avg_score = 0
        if percentage_count_by_teacher.get(teacher_user_id, 0) > 0:
            avg_score = round(
                percentage_sum_by_teacher[teacher_user_id] / percentage_count_by_teacher[teacher_user_id],
                1,
            )
        if total_uploads > 0 or submission_count > 0 or avg_score > 0:
            active_teachers_with_activity += 1

        teacher_activity_rows.append(
            {
                "teacher_name": teacher_profile.user.get_full_name() or teacher_profile.user.username,
                "class_names": class_names,
                "homework": homework_count,
                "assignments": assignment_count,
                "quizzes": quiz_count,
                "results": result_count,
                "submissions": submission_count,
                "pending_submissions": pending_count,
                "total_uploads": total_uploads,
                "avg_score": avg_score,
            }
        )
    teacher_activity_rows.sort(
        key=lambda item: (item["total_uploads"], item["submissions"], item["avg_score"]),
        reverse=True,
    )

    performance_percentages = []
    for row in Result.objects.exclude(total_marks__lte=0).values("marks", "total_marks"):
        performance_percentages.append((row["marks"] / row["total_marks"]) * 100)
    student_performance_average = round(sum(performance_percentages) / len(performance_percentages), 1) if performance_percentages else 0
    overall_attendance_rows = build_overall_attendance_rows(Student.objects.all())
    overall_attendance_summary = summarize_overall_attendance(overall_attendance_rows)

    dashboard_stats = [
        {
            "icon": "bi bi-people-fill",
            "value": students_count,
            "label": "Total Students",
            "meta": "Active student records",
            "href": reverse("student_list"),
            "cta": "View Students",
        },
        {
            "icon": "bi bi-person-workspace",
            "value": teachers_count,
            "label": "Total Teachers",
            "meta": "Faculty accounts",
            "href": reverse("teacher_list"),
            "cta": "View Teachers",
        },
        {
            "icon": "bi bi-calendar-check-fill",
            "value": today_attendance if (today_attendance := today_stats["marked_count"]) else 0,
            "label": "Attendance Today",
            "meta": "Marked attendance records",
            "href": reverse("attendance_report"),
            "cta": "View Report",
        },
        {
            "icon": "bi bi-clock-fill",
            "value": today_stats["unmarked_count"],
            "label": "Pending Tasks",
            "meta": "Unmarked attendance",
            "href": reverse("attendance_report"),
            "cta": "Resolve Now",
        },
        {
            "icon": "bi bi-graph-up-arrow",
            "value": f"{overall_attendance_summary['overall_percentage']}%",
            "label": "Overall Attendance",
            "meta": "Across all students",
            "href": reverse("attendance_report"),
            "cta": "View Analytics",
        },
    ]

    dashboard_cards = [
        {
            "icon": "bi bi-people-fill",
            "title": "Students",
            "description": "Open student records, profiles, and class lists.",
            "href": reverse("student_list"),
        },
        {
            "icon": "bi bi-person-workspace",
            "title": "Manage Teachers",
            "description": "Control teacher accounts and class assignments.",
            "href": reverse("teacher_list"),
        },
        {
            "icon": "bi bi-diagram-3-fill",
            "title": "Class Controls",
            "description": "Assign multiple teachers and one attendance owner per class.",
            "href": reverse("class_assignment_list"),
        },
        {
            "icon": "bi bi-journal-richtext",
            "title": "Enrollment",
            "description": "Review and process student admissions quickly.",
            "href": reverse("student_admissions"),
        },
        {
            "icon": "bi bi-journal-check",
            "title": "Assignments",
            "description": "Monitor assignment activity, submissions, and deadlines by teacher.",
            "href": reverse("assignment_list"),
        },
        {
            "icon": "bi bi-ui-checks-grid",
            "title": "Quiz System",
            "description": "View quiz attempts and teacher performance analytics.",
            "href": reverse("quiz_list"),
        },
        {
            "icon": "bi bi-camera-video-fill",
            "title": "Live Attendance",
            "description": "Track live recognition and classroom activity.",
            "href": reverse("live_attendance"),
        },
    ]

    context = {
        "students_count": students_count,
        "teachers_count": teachers_count,
        "assigned_teachers_count": assigned_teachers_count,
        "unassigned_teachers_count": teachers_count - assigned_teachers_count,
        "today_attendance": today_stats["marked_count"],
        "today_present_count": today_stats["present_count"],
        "today_absent_count": today_stats["absent_count"],
        "today_unmarked_count": today_stats["unmarked_count"],
        "recent_attendance": recent_attendance,
        "dashboard_header": get_dashboard_header("ADMIN"),
        "dashboard_topbar_actions": get_dashboard_topbar_actions("ADMIN"),
        "dashboard_stats": dashboard_stats,
        "dashboard_cards": dashboard_cards,
        "overall_attendance_percentage": overall_attendance_summary["overall_percentage"],
        "overall_attendance_students_with_records": overall_attendance_summary["students_with_records"],
        "overall_attendance_good_count": overall_attendance_summary["good_count"],
        "overall_attendance_average_count": overall_attendance_summary["average_count"],
        "overall_attendance_low_count": overall_attendance_summary["low_count"],
        "overall_attendance_rows": overall_attendance_rows[:12],
        "total_assignments_all": total_assignments,
        "total_quizzes_all": total_quizzes,
        "active_teachers_with_activity": active_teachers_with_activity,
        "total_assignment_submissions_all": total_submissions,
        "total_homework_all": total_homework,
        "total_results_all": total_results,
        "total_pending_submissions_all": total_pending_submissions,
        "student_performance_average": student_performance_average,
        "teacher_activity_rows": teacher_activity_rows,
    }

    LOGGER.info(
        "Admin dashboard stats: date=%s students=%s attendance_today=%s present_today=%s absent_today=%s not_marked_today=%s",
        today, students_count, today_stats["marked_count"],
        today_stats["present_count"], today_stats["absent_count"], today_stats["unmarked_count"],
    )

    return render(request, "accounts/dashboard.html", context)


# =========================================================
# TEACHER DASHBOARD
# =========================================================

@login_required
@user_passes_test(is_teacher)
def teacher_dashboard(request):
    """Display teacher dashboard with class-specific statistics and charts."""
    teacher = get_teacher_profile(request.user)
    if teacher is None:
        messages.error(request, "Teacher profile is missing. Please contact support.")
        return _render_teacher_dashboard_empty(request, class_names=[], missing_profile=True)

    class_roles = get_teacher_class_roles(teacher)
    class_names = [item["name"] for item in class_roles]
    attendance_class_names = [item["name"] for item in class_roles if item["is_attendance_teacher"]]

    if not class_names:
        return _render_teacher_dashboard_empty(request, class_names, missing_profile=False)

    today = localdate()
    students = Student.objects.filter(class_name__in=class_names).select_related("user")
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
        teacher_attendance.select_related("student__user")
        .order_by("-date", "-marked_at", "-id")[:5]
    )
    overall_attendance_rows = build_overall_attendance_rows(students)
    overall_attendance_summary = summarize_overall_attendance(overall_attendance_rows)

    dashboard_cards = []
    if attendance_class_names:
        dashboard_cards.append(
            {
                "icon": "bi bi-clipboard-check-fill",
                "title": "Mark Attendance",
                "description": f"You control attendance in {len(attendance_class_names)} class(es).",
                "href": reverse("mark_attendance"),
            }
        )
    dashboard_cards.extend(
        [
            {
                "icon": "bi bi-journal-check",
                "title": "Assignments",
                "description": "Create assignments and track submitted, late, and pending work.",
                "href": reverse("assignment_list"),
            },
            {
                "icon": "bi bi-ui-checks-grid",
                "title": "Quiz System",
                "description": "Create quizzes, add MCQs, and review instant results.",
                "href": reverse("quiz_list"),
            },
            {
                "icon": "bi bi-cloud-arrow-up-fill",
                "title": "Upload Homework",
                "description": "Publish assignments with due dates for each assigned class.",
                "href": reverse("upload_homework"),
            },
            {
                "icon": "bi bi-journal-plus",
                "title": "Add Results",
                "description": "Create and manage exam result entries for your classes.",
                "href": reverse("add_result"),
            },
            {
                "icon": "bi bi-diagram-3-fill",
                "title": "My Classes",
                "description": "View class ownership and attendance-control labels.",
                "href": reverse("teacher_classes"),
            },
        ]
    )

    context = {
        "total_students": total_students,
        "today_present": today_present,
        "today_absent": today_absent,
        "total_attendance": total_attendance,
        "recent_attendance": recent_attendance,
        "teacher_classes": class_names,
        "teacher_class_roles": class_roles,
        "attendance_class_names": attendance_class_names,
        "attendance_controlled_count": len(attendance_class_names),
        "students": students,
        "class_counts": class_counts,
        "using_default_password": request.user.check_password(DEFAULT_PASSWORD),
        "dashboard_header": get_dashboard_header("TEACHER"),
        "dashboard_topbar_actions": get_dashboard_topbar_actions("TEACHER"),
        "dashboard_stats": [
            {
                "icon": "bi bi-book-fill",
                "value": len(class_names),
                "label": "Assigned Classes",
                "meta": "Active teaching classes",
                "href": reverse("teacher_classes"),
                "cta": "View Classes",
            },
            {
                "icon": "bi bi-clipboard-check-fill",
                "value": len(attendance_class_names),
                "label": "Attendance Control",
                "meta": "Classes where you can mark attendance",
                "href": reverse("teacher_classes"),
                "cta": "Review Roles",
            },
            {
                "icon": "bi bi-people-fill",
                "value": total_students,
                "label": "Total Students",
                "meta": "Across your classes",
                "href": reverse("view_students"),
                "cta": "View Students",
            },
            {
                "icon": "bi bi-check-circle-fill",
                "value": today_present,
                "label": "Present Today",
                "meta": "Students marked present",
                "href": reverse("attendance_report"),
                "cta": "Open Report",
            },
            {
                "icon": "bi bi-x-circle-fill",
                "value": today_absent,
                "label": "Absent Today",
                "meta": "Students marked absent",
                "href": reverse("attendance_report"),
                "cta": "Review",
            },
            {
                "icon": "bi bi-graph-up-arrow",
                "value": f"{overall_attendance_summary['overall_percentage']}%",
                "label": "Overall Attendance",
                "meta": "Across assigned classes",
                "href": reverse("attendance_report"),
                "cta": "Analyze",
            },
        ],
        "dashboard_cards": dashboard_cards,
        "overall_attendance_percentage": overall_attendance_summary["overall_percentage"],
        "overall_attendance_students_with_records": overall_attendance_summary["students_with_records"],
        "overall_attendance_good_count": overall_attendance_summary["good_count"],
        "overall_attendance_average_count": overall_attendance_summary["average_count"],
        "overall_attendance_low_count": overall_attendance_summary["low_count"],
        "overall_attendance_rows": overall_attendance_rows[:12],
    }

    LOGGER.info(
        "Teacher dashboard stats: user_id=%s classes=%s attendance_classes=%s date=%s students=%s present=%s absent=%s total_attendance=%s",
        request.user.id,
        ",".join(class_names),
        ",".join(attendance_class_names),
        today,
        total_students,
        today_present,
        today_absent,
        total_attendance,
    )

    return render(request, "accounts/dashboard.html", context)


def _render_teacher_dashboard_empty(request, class_names, *, missing_profile=False):
    """Render teacher dashboard with empty state when profile/classes are missing."""
    if missing_profile:
        messages.warning(request, "Your teacher profile is not configured yet.")
    else:
        messages.warning(request, "You don't have a class assigned. Please contact support.")

    default_data = {
        "total_students": 0, "today_present": 0, "today_absent": 0,
        "total_attendance": 0, "recent_attendance": [],
        "teacher_classes": class_names, "students": [], "class_counts": {},
        "teacher_class_roles": [],
        "attendance_class_names": [],
        "attendance_controlled_count": 0,
        "using_default_password": request.user.check_password(DEFAULT_PASSWORD),
        "dashboard_header": get_dashboard_header("TEACHER"),
        "dashboard_topbar_actions": get_dashboard_topbar_actions("TEACHER"),
        "dashboard_stats": [],
        "dashboard_cards": [],
        "overall_attendance_percentage": 0,
        "overall_attendance_students_with_records": 0,
        "overall_attendance_good_count": 0,
        "overall_attendance_average_count": 0,
        "overall_attendance_low_count": 0,
        "overall_attendance_rows": [],
    }
    return render(request, "accounts/dashboard.html", default_data)


@login_required
@user_passes_test(is_teacher)
def teacher_classes(request):
    """Display classes assigned to the current teacher."""
    teacher = get_teacher_profile(request.user)
    if teacher is None:
        messages.error(request, "Teacher profile is missing. Please contact support.")
        return render(request, "accounts/teacher_classes.html", {
            "classes_data": [],
            "teacher_classes": [],
        })

    class_roles = get_teacher_class_roles(teacher)
    class_names = [item["name"] for item in class_roles]
    class_roles_by_name = {item["name"]: item for item in class_roles}

    classes_data = []
    for class_name in class_names:
        students = Student.objects.filter(class_name=class_name)
        role_details = class_roles_by_name.get(class_name, {})
        classes_data.append({
            "name": class_name,
            "student_count": students.count(),
            "students": students,
            "is_attendance_teacher": role_details.get("is_attendance_teacher", False),
            "role_label": role_details.get("role_label", "Subject Teacher"),
            "attendance_teacher_name": role_details.get("attendance_teacher_name", "-"),
        })

    context = {
        "classes_data": classes_data,
        "teacher_classes": class_names,
        "attendance_class_names": [item["name"] for item in class_roles if item["is_attendance_teacher"]],
    }
    return render(request, "accounts/teacher_classes.html", context)


# =========================================================
# STUDENT DASHBOARD
# =========================================================

@login_required
@user_passes_test(is_student)
def student_dashboard(request):
    """Display student dashboard with personal statistics."""
    student = get_student_profile(request.user)

    if not student:
        messages.error(request, "Student profile not found.")
        return redirect("login")

    today = localdate()
    attendance_qs = Attendance.objects.filter(student=student).order_by("-date", "-marked_at", "-id")
    attendance_count = attendance_qs.count()
    present_count = attendance_qs.filter(status="Present").count()
    absent_count = max(attendance_count - present_count, 0)
    attendance_percentage = round((present_count / attendance_count) * 100, 1) if attendance_count else 0
    overall_attendance_status, overall_attendance_status_class = resolve_attendance_health(attendance_percentage)

    results_qs = Result.objects.filter(student=student).order_by("-date", "-id")
    results_count = results_qs.count()

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

    return render(request, "accounts/dashboard.html", {
        "student": student,
        "attendance_count": attendance_count,
        "attendance_percentage": attendance_percentage,
        "overall_attendance_percentage": attendance_percentage,
        "overall_attendance_present_count": present_count,
        "overall_attendance_absent_count": absent_count,
        "overall_attendance_status": overall_attendance_status,
        "overall_attendance_status_class": overall_attendance_status_class,
        "results_count": results_count,
        "recent_homework": recent_homework,
        "recent_attendance": recent_attendance,
        "homework_count": homeworks.count(),
        "using_default_password": request.user.check_password(DEFAULT_PASSWORD),
        "dashboard_header": get_dashboard_header("STUDENT"),
        "dashboard_topbar_actions": get_dashboard_topbar_actions("STUDENT", student_id=student.id),
        "dashboard_stats": [
            {
                "icon": "bi bi-calendar-check-fill",
                "value": f"{attendance_percentage}%",
                "label": "Attendance Rate",
                "meta": f"{attendance_count} records",
                "href": reverse("student_attendance"),
                "cta": "View History",
            },
            {
                "icon": "bi bi-trophy-fill",
                "value": results_count,
                "label": "Total Results",
                "meta": "Published exam records",
                "href": reverse("result_list"),
                "cta": "View Results",
            },
            {
                "icon": "bi bi-journal-text",
                "value": homeworks.count(),
                "label": "Active Homework",
                "meta": "Pending assignments",
                "href": reverse("homework_list"),
                "cta": "Open Homework",
            },
            {
                "icon": "bi bi-person-circle",
                "value": "100%",
                "label": "Profile Complete",
                "meta": "Student profile status",
                "href": reverse("student_profile", kwargs={"id": student.id}),
                "cta": "View Profile",
            },
        ],
        "dashboard_cards": [
            {
                "icon": "bi bi-calendar-check-fill",
                "title": "My Attendance",
                "description": "Review attendance history and percentage.",
                "href": reverse("student_attendance"),
            },
            {
                "icon": "bi bi-journal-text",
                "title": "Homework",
                "description": "Open assignments and due dates quickly.",
                "href": reverse("homework_list"),
            },
            {
                "icon": "bi bi-journal-check",
                "title": "Assignments",
                "description": "View assigned tasks, deadlines, and submission status.",
                "href": reverse("assignment_list"),
            },
            {
                "icon": "bi bi-ui-checks-grid",
                "title": "Quizzes",
                "description": "Attempt quizzes and view instant score reports.",
                "href": reverse("quiz_list"),
            },
            {
                "icon": "bi bi-trophy-fill",
                "value": results_count,
                "label": "Total Results",
                "meta": "Published exam records",
                "href": reverse("result_list"),
            },
            {
                "icon": "bi bi-person-circle",
                "title": "Profile",
                "description": "View your student profile details.",
                "href": reverse("student_profile", kwargs={"id": student.id}),
            },
        ],
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
def class_assignment_list(request):
    """Class-centric assignment control for teachers and attendance owner."""
    classrooms = Classroom.objects.select_related("attendance_teacher__user").prefetch_related("teachers__user").order_by("name")
    return render(
        request,
        "accounts/class_assignment_list.html",
        {
            "classrooms": classrooms,
            "total_classes": classrooms.count(),
        },
    )


@login_required
@user_passes_test(is_admin)
def manage_class_assignment(request, class_id):
    """Manage assigned teachers and attendance teacher for one class."""
    classroom = get_object_or_404(
        Classroom.objects.select_related("attendance_teacher__user").prefetch_related("teachers__user"),
        id=class_id,
    )
    teachers = Teacher.objects.select_related("user").order_by("user__first_name", "user__last_name", "user__username")

    if request.method == "POST":
        selected_teacher_ids = set()
        for raw_id in request.POST.getlist("teacher_ids"):
            try:
                selected_teacher_ids.add(int(raw_id))
            except (TypeError, ValueError):
                continue

        selected_teachers = teachers.filter(id__in=selected_teacher_ids)
        attendance_teacher_raw = (request.POST.get("attendance_teacher") or "").strip()
        attendance_teacher = None
        if attendance_teacher_raw:
            try:
                attendance_teacher = teachers.filter(id=int(attendance_teacher_raw)).first()
            except (TypeError, ValueError):
                attendance_teacher = None

        if attendance_teacher and attendance_teacher.id not in selected_teacher_ids:
            messages.error(request, "Attendance teacher must also be included in assigned teachers.")
        else:
            classroom.teachers.set(selected_teachers)
            classroom.attendance_teacher = attendance_teacher
            classroom.save(update_fields=["attendance_teacher"])
            messages.success(request, f"Class assignments saved for {classroom.name}.")
            return redirect("class_assignment_list")

    return render(
        request,
        "accounts/manage_class_assignment.html",
        {
            "classroom": classroom,
            "teachers": teachers,
            "assigned_ids": set(classroom.teachers.values_list("id", flat=True)),
            "attendance_teacher_id": classroom.attendance_teacher_id,
        },
    )


@login_required
@user_passes_test(is_admin)
def assign_teacher_classes(request, teacher_id):
    """Assign or unassign classes to a teacher."""
    teacher = get_object_or_404(Teacher, id=teacher_id)
    classrooms = Classroom.objects.order_by("name")

    if request.method == "POST":
        previous_class_ids = set(teacher.classes.values_list("id", flat=True))
        selected_class_ids = set()
        for raw_id in request.POST.getlist("class_ids"):
            try:
                selected_class_ids.add(int(raw_id))
            except (TypeError, ValueError):
                continue

        teacher.classes.set(classrooms.filter(id__in=selected_class_ids))
        removed_class_ids = previous_class_ids - selected_class_ids
        if removed_class_ids:
            Classroom.objects.filter(id__in=removed_class_ids, attendance_teacher=teacher).update(attendance_teacher=None)

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
    return reset_user_password(request, Student, student_id, "accounts/credentials_reset_done.html")


@login_required
@user_passes_test(is_admin)
def reset_teacher_password(request, teacher_id):
    """Reset a teacher's password."""
    return reset_user_password(request, Teacher, teacher_id, "accounts/credentials_reset_done.html")


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

    is_own_profile = (
        get_user_role(request.user) == "STUDENT"
        and getattr(request.user, "student", None) is not None
        and request.user.student.id == student.id
    )
    can_edit_profile = is_admin(request.user) or is_own_profile
    if is_admin(request.user):
        profile_edit_url = reverse("admin_edit_student", kwargs={"student_id": student.id})
    elif is_own_profile:
        profile_edit_url = reverse("edit_profile")
    else:
        profile_edit_url = None

    return render(request, "accounts/student_profile.html", {
        "student": student,
        "attendances": attendances,
        "present_count": present_count,
        "absent_count": absent_count,
        "percentage": round(percentage, 2),
        "can_edit_admission": is_admin(request.user),
        "can_edit_profile": can_edit_profile,
        "profile_edit_url": profile_edit_url,
        "show_parent_contact": get_user_role(request.user) != "TEACHER",
    })


@login_required
def edit_student_profile(request, student_id=None):
    """
    Edit student profile with role-aware access.
    - Students can edit their own profile.
    - Admin can edit any student profile.
    """
    role = get_user_role(request.user)

    if role == "ADMIN":
        if student_id is None:
            messages.error(request, "Please choose a student profile to edit.")
            return redirect("student_admissions")
        student = get_object_or_404(get_student_queryset(), id=student_id)
        form_class = AdminStudentProfileForm
    elif role == "STUDENT":
        student = Student.objects.select_related("user").filter(user=request.user).first()
        if student is None:
            messages.error(request, "Student profile not found.")
            return redirect("login")
        if student_id is not None and student_id != student.id:
            messages.error(request, "You are not allowed to edit another student's profile.")
            return redirect("edit_profile")
        if student.user_id != request.user.id:
            raise PermissionDenied("You are not allowed to edit this profile.")
        form_class = StudentProfileForm
    else:
        messages.error(request, "You are not allowed to edit student profiles.")
        return redirect(_get_redirect_url(request.user))

    if request.method == "POST":
        previous_image = student.image if student.image else None
        form = form_class(request.POST, request.FILES, instance=student)
        if form.is_valid():
            updated_student = form.save()
            if (
                previous_image
                and "image" in form.changed_data
                and previous_image.name
                and previous_image.name != (updated_student.image.name if updated_student.image else "")
            ):
                previous_image.delete(save=False)
            messages.success(request, "Profile updated successfully.")
            return redirect("student_profile", id=student.id)
    else:
        form = form_class(instance=student)

    return render(
        request,
        "accounts/edit_student_profile.html",
        {
            "form": form,
            "student": student,
            "is_admin_editor": role == "ADMIN",
        },
    )


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
        teacher = get_teacher_profile(request.user)
        if teacher is None:
            messages.error(request, "Teacher profile is missing. Please contact support.")
            students = students.none()
        else:
            class_names = get_teacher_class_names(teacher)
            students = students.filter(class_name__in=class_names)

    context = {
        'students': students,
    }
    return render(request, 'accounts/view_students.html', context)


@login_required
def quick_search(request):
    """
    Role-aware quick search endpoint used by the topbar.
    """
    query = (request.GET.get("q") or "").strip()
    if len(query) < 2:
        return JsonResponse({"results": []})

    role = get_user_role(request.user)
    results = []
    teacher_profile = getattr(request.user, "teacher", None) if role == "TEACHER" else None
    if role == "TEACHER" and teacher_profile is None:
        return JsonResponse({"results": []})

    def add_result(result_type, label, description, href, icon):
        if len(results) >= 14:
            return
        results.append(
            {
                "type": result_type,
                "label": label,
                "description": description,
                "href": href,
                "icon": icon,
            }
        )

    if role in {"ADMIN", "TEACHER"}:
        student_qs = Student.objects.select_related("user").filter(
            Q(full_name__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__username__icontains=query)
            | Q(roll_number__icontains=query)
            | Q(class_name__icontains=query)
        )

        if role == "TEACHER":
            teacher_class_names = get_teacher_class_names(teacher_profile)
            student_qs = student_qs.filter(class_name__in=teacher_class_names)

        for student in student_qs.order_by("class_name", "roll_number")[:6]:
            add_result(
                "Student",
                student.display_name,
                f"Class {student.class_name} - Roll {student.roll_number}",
                reverse("student_profile", kwargs={"id": student.id}),
                "bi bi-person-badge-fill",
            )

    if role == "ADMIN":
        for teacher in Teacher.objects.select_related("user").filter(
            Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__username__icontains=query)
            | Q(subject__icontains=query)
            | Q(phone__icontains=query)
        )[:4]:
            add_result(
                "Teacher",
                teacher.user.get_full_name() or teacher.user.username,
                f"{teacher.subject} - {teacher.phone}",
                reverse("teacher_list"),
                "bi bi-person-workspace",
            )

        for classroom in Classroom.objects.filter(name__icontains=query)[:4]:
            add_result(
                "Class",
                classroom.name,
                "Classroom",
                reverse("student_admissions") + f"?class_id={classroom.id}",
                "bi bi-diagram-3-fill",
            )

    if role in {"ADMIN", "TEACHER", "STUDENT"}:
        if role == "STUDENT":
            student = Student.objects.filter(user=request.user).first()
            if student:
                homework_qs = Homework.objects.filter(class_name=student.class_name)
                result_qs = Result.objects.filter(student=student)
            else:
                homework_qs = Homework.objects.none()
                result_qs = Result.objects.none()
        elif role == "TEACHER":
            homework_qs = Homework.objects.filter(teacher=teacher_profile)
            result_qs = Result.objects.filter(student__class_name__in=get_teacher_class_names(teacher_profile))
        else:
            homework_qs = Homework.objects.all()
            result_qs = Result.objects.all()

        for homework in homework_qs.filter(
            Q(title__icontains=query) | Q(subject__icontains=query) | Q(class_name__icontains=query)
        ).order_by("-date_assigned")[:3]:
            add_result(
                "Homework",
                homework.title,
                f"{homework.subject} - Class {homework.class_name}",
                reverse("homework_list"),
                "bi bi-journal-text",
            )

        for result in result_qs.filter(
            Q(subject__icontains=query)
            | Q(exam_type__icontains=query)
            | Q(student__full_name__icontains=query)
        ).select_related("student__user").order_by("-date")[:3]:
            student_name = result.student.display_name
            add_result(
                "Result",
                f"{result.subject} - {student_name}",
                f"{result.exam_type} - {result.marks}/{result.total_marks}",
                reverse("result_list"),
                "bi bi-trophy-fill",
            )

    return JsonResponse({"results": results})


# =========================================================
# SEPARATE PAGES FOR SIDEBAR
# =========================================================

def attendance_page(request):
    """Attendance overview page."""
    return render(request, "accounts/attendance.html", {
        "dashboard_header": get_dashboard_header("ADMIN"),
    })


def results_page(request):
    """Results overview page."""
    return render(request, "accounts/results.html", {
        "dashboard_header": get_dashboard_header("ADMIN"),
    })


def homework_page(request):
    """Homework overview page."""
    return render(request, "accounts/homework.html", {
        "dashboard_header": get_dashboard_header("ADMIN"),
    })
