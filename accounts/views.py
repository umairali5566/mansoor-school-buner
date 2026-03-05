from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.hashers import make_password
from django.utils.crypto import get_random_string
from django.contrib import messages
from django.views.decorators.http import require_POST
from datetime import date, timedelta
import json

from .models import CustomUser, Student, Teacher
from .forms import StudentCreateForm, TeacherCreateForm
from attendance.models import Attendance, StudentFaceData
from results.models import Result
from homework.models import Homework


# =========================================================
# ROLE CHECK FUNCTIONS
# =========================================================

def is_admin(user):
    return user.is_authenticated and user.role == "ADMIN"

def is_teacher(user):
    return user.is_authenticated and user.role == "TEACHER"

def is_student(user):
    return user.is_authenticated and user.role == "STUDENT"


# =========================================================
# LOGIN VIEW
# =========================================================

def login_view(request):

    if request.user.is_authenticated:
        if request.user.role == "ADMIN":
            return redirect("admin_dashboard")
        elif request.user.role == "TEACHER":
            return redirect("teacher_dashboard")
        elif request.user.role == "STUDENT":
            return redirect("student_dashboard")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)

            if user.role == "ADMIN":
                return redirect("admin_dashboard")
            elif user.role == "TEACHER":
                return redirect("teacher_dashboard")
            elif user.role == "STUDENT":
                return redirect("student_dashboard")
        else:
            messages.error(request, "Invalid Username or Password")

    return render(request, "accounts/login.html")


# =========================================================
# LOGOUT
# =========================================================

@require_POST
@login_required
def logout_view(request):
    logout(request)
    return redirect("login")


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):

    students_count = Student.objects.count()
    teachers_count = Teacher.objects.count()

    today = date.today()
    today_attendance = Attendance.objects.filter(date=today).count()

    present_count = Attendance.objects.filter(status="Present").count()
    absent_count = Attendance.objects.filter(status="Absent").count()

    context = {
        "students_count": students_count,
        "teachers_count": teachers_count,
        "today_attendance": today_attendance,
        "present_count": present_count,
        "absent_count": absent_count,
    }

    return render(request, "accounts/admin_dashboard.html", context)


# =========================================================
# TEACHER DASHBOARD
# =========================================================
from accounts.models import Student
from attendance.models import Attendance
from django.db.models import Count
from datetime import date
@login_required
@user_passes_test(is_teacher)
def teacher_dashboard(request):

    today = date.today()

    # =========================
    # Basic Stats
    # =========================

    total_students = Student.objects.count()

    today_present = Attendance.objects.filter(
        date=today,
        status="Present"
    ).count()

    today_absent = Attendance.objects.filter(
        date=today,
        status="Absent"
    ).count()

    total_attendance = Attendance.objects.count()

    # =========================
    # Recent Attendance
    # =========================

    recent_attendance = Attendance.objects.select_related(
        "student"
    ).order_by("-date")[:5]

    # =========================
    # Today Chart
    # =========================

    today_chart_data = json.dumps([today_present, today_absent])

    # =========================
    # Weekly Attendance
    # =========================

    weekly_labels = []
    weekly_present = []
    weekly_absent = []

    for i in range(6, -1, -1):

        day = today - timedelta(days=i)

        weekly_labels.append(day.strftime("%b %d"))

        present_count = Attendance.objects.filter(
            date=day,
            status="Present"
        ).count()

        absent_count = Attendance.objects.filter(
            date=day,
            status="Absent"
        ).count()

        weekly_present.append(present_count)
        weekly_absent.append(absent_count)

    # =========================
    # Monthly Attendance
    # =========================

    monthly_labels = []
    monthly_present = []

    for i in range(29, -1, -1):

        day = today - timedelta(days=i)

        monthly_labels.append(day.strftime("%b %d"))

        present_count = Attendance.objects.filter(
            date=day,
            status="Present"
        ).count()

        monthly_present.append(present_count)

    # =========================
    # Class Wise Attendance (NEW)
    # =========================

    class_attendance = (
        Attendance.objects
        .filter(date=today)
        .values("student__class_name", "status")
        .annotate(total=Count("id"))
    )

    classes = {}

    for record in class_attendance:

        cls = record["student__class_name"]
        status = record["status"]
        total = record["total"]

        if cls not in classes:
            classes[cls] = {"Present": 0, "Absent": 0}

        classes[cls][status] = total

    class_labels = list(classes.keys())

    class_present = [classes[c]["Present"] for c in class_labels]
    class_absent = [classes[c]["Absent"] for c in class_labels]

    # =========================
    # Context
    # =========================

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
    }

    return render(request, "accounts/teacher_dashboard.html", context)
# =========================================================
# STUDENT DASHBOARD
# =========================================================

@login_required
@user_passes_test(is_student)
def student_dashboard(request):

    user = request.user
    student = Student.objects.filter(user=user).first()

    if not student:
        messages.error(request, "Student profile not found.")
        return redirect("login")

    face = StudentFaceData.objects.filter(student=student).first()

    attendance_count = Attendance.objects.filter(student=student).count()
    results_count = Result.objects.filter(student=student).count()
    homeworks = Homework.objects.all().order_by("-date_assigned")
    homework_count = homeworks.count()

    context = {
        "student": student,
        "face": face,
        "attendance_count": attendance_count,
        "results_count": results_count,
        "homeworks": homeworks, 
        "homework_count": homework_count, 
    }

    return render(request, "accounts/student_dashboard.html", context)


@login_required
@user_passes_test(is_admin)
def student_list(request):
    students = Student.objects.all()
    return render(request, "accounts/student_list.html", {"students": students})


@login_required
@user_passes_test(is_admin)
def add_student(request):
    if request.method == "POST":
        form = StudentCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            password = form.generated_password

            return render(request, "accounts/student_created.html", {
                "username": user.username,
                "password": password
            })
    else:
        form = StudentCreateForm()

    return render(request, "accounts/add_student.html", {"form": form})


@login_required
@user_passes_test(is_admin)
def edit_student(request, student_id):
    student = get_object_or_404(Student, id=student_id)

    if request.method == "POST":
        student.user.username = request.POST.get("username")
        student.roll_number = request.POST.get("roll_number")
        student.class_name = request.POST.get("class_name")
        student.phone = request.POST.get("phone")

        student.user.save()
        student.save()

        return redirect("student_list")

    return render(request, "accounts/edit_student.html", {"student": student})


@login_required
@user_passes_test(is_admin)
def delete_student(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    student.user.delete()
    return redirect("student_list")

    
@login_required
@user_passes_test(is_admin)
def student_list(request):
    students = Student.objects.all()
    return render(request, "accounts/student_list.html", {"students": students})


@login_required
@user_passes_test(is_admin)
def add_student(request):
    if request.method == "POST":
        form = StudentCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            password = form.generated_password

            return render(request, "accounts/student_created.html", {
                "username": user.username,
                "password": password
            })
    else:
        form = StudentCreateForm()

    return render(request, "accounts/add_student.html", {"form": form})


@login_required
@user_passes_test(is_admin)
def edit_student(request, student_id):
    student = get_object_or_404(Student, id=student_id)

    if request.method == "POST":
        student.user.username = request.POST.get("username")
        student.roll_number = request.POST.get("roll_number")
        student.class_name = request.POST.get("class_name")
        student.phone = request.POST.get("phone")

        student.user.save()
        student.save()

        return redirect("student_list")

    return render(request, "accounts/edit_student.html", {"student": student})


@login_required
@user_passes_test(is_admin)
def delete_student(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    student.user.delete()
    return redirect("student_list")


@login_required
@user_passes_test(is_admin)
def teacher_list(request):
    teachers = Teacher.objects.all()
    return render(request, "accounts/teacher_list.html", {"teachers": teachers})


@login_required
@user_passes_test(is_admin)
def add_teacher(request):
    if request.method == "POST":
        form = TeacherCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            password = form.generated_password

            return render(request, "accounts/teacher_created.html", {
                "username": user.username,
                "password": password
            })
    else:
        form = TeacherCreateForm()

    return render(request, "accounts/add_teacher.html", {"form": form})


@login_required
@user_passes_test(is_admin)
def edit_teacher(request, teacher_id):
    teacher = get_object_or_404(Teacher, id=teacher_id)

    if request.method == "POST":
        teacher.user.username = request.POST.get("username")
        teacher.subject = request.POST.get("subject")
        teacher.phone = request.POST.get("phone")

        teacher.user.save()
        teacher.save()

        return redirect("teacher_list")

    return render(request, "accounts/edit_teacher.html", {"teacher": teacher})


@login_required
@user_passes_test(is_admin)
def delete_teacher(request, teacher_id):
    teacher = get_object_or_404(Teacher, id=teacher_id)
    teacher.user.delete()
    return redirect("teacher_list")



@login_required
@user_passes_test(is_admin)
def reset_student_password(request, student_id):

    student = get_object_or_404(Student, id=student_id)

    new_password = get_random_string(8)
    student.user.password = make_password(new_password)
    student.user.save()

    return render(request, "accounts/password_reset_done.html", {
        "username": student.user.username,
        "password": new_password
    })



@login_required
@user_passes_test(is_admin)
def reset_teacher_password(request, teacher_id):

    teacher = get_object_or_404(Teacher, id=teacher_id)

    new_password = get_random_string(8)
    teacher.user.password = make_password(new_password)
    teacher.user.save()

    return render(request, "accounts/password_reset_done.html", {
        "username": teacher.user.username,
        "password": new_password
    })


#import face_recognition
import numpy as np
from attendance.models import StudentFaceData

@login_required
def student_profile(request):
    user = request.user
    student = Student.objects.get(user=user)

    if request.method == "POST":

        # Update phone
        phone = request.POST.get("phone")
        if phone:
            student.phone = phone

        # Update face image
        if request.FILES.get("face_image"):
            student.face_image = request.FILES.get("face_image")
            student.save()   # Save first (important)

            # 🔥 STEP 3 — ENCODING SAVE
            image = face_recognition.load_image_file(student.face_image.path)
            encodings = face_recognition.face_encodings(image)

            if encodings:
                encoding_bytes = encodings[0].tobytes()

                StudentFaceData.objects.update_or_create(
                    student=student,
                    defaults={"encoding": encoding_bytes}
                )

        student.save()

        messages.success(request, "Profile Updated Successfully ✅")
        return redirect("student_dashboard")

    context = {
        "student": student
    }

    return render(request, "accounts/student_profile.html", context)

def attendance_report(request):

    records = Attendance.objects.all()

    present_count = records.filter(status="Present").count()
    absent_count = records.filter(status="Absent").count()

    classes = Student.objects.values_list("class_name", flat=True).distinct()

    selected_date = request.GET.get("date")
    selected_class = request.GET.get("class")

    context = {
        "attendances": records,
        "present_count": present_count,
        "absent_count": absent_count,
        "classes": classes,
        "selected_date": selected_date,
        "selected_class": selected_class,
    }

    return render(request, "attendance/attendance_report.html", context)