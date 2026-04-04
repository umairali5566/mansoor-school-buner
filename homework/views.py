import os
from datetime import date

from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Homework


# =========================
# Upload Homework (Teacher)
# =========================
@login_required
def upload_homework(request):

    # Only teachers can upload
    if not hasattr(request.user, 'teacher'):
        return redirect('teacher_dashboard')

    teacher = request.user.teacher
    class_names = list(teacher.classes.values_list('name', flat=True))
    if not class_names:
        messages.error(request, "Cannot upload homework until your class is assigned.")
        return redirect('teacher_dashboard')

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()
        subject = request.POST.get("subject", "").strip()
        due_date_raw = request.POST.get("due_date")
        file = request.FILES.get("file")
        class_name = request.POST.get("class_name") or class_names[0]

        if class_name not in class_names:
            messages.error(request, "Invalid class selected.")
            return render(request, "homework/upload_homework.html", {"class_names": class_names})

        if not title or not description or not subject or not due_date_raw or not file:
            messages.error(request, "Title, description, class, subject, due date and file are required.")
            return render(request, "homework/upload_homework.html", {"class_names": class_names})
        try:
            due_date = date.fromisoformat(due_date_raw)
        except ValueError:
            messages.error(request, "Invalid due date.")
            return render(request, "homework/upload_homework.html", {"class_names": class_names})

        Homework.objects.create(
            title=title,
            description=description,
            class_name=class_name,
            subject=subject,
            teacher=teacher,
            file=file,
            due_date=due_date,
        )

        messages.success(request, "Homework uploaded successfully.")
        return redirect("teacher_dashboard")

    return render(request, "homework/upload_homework.html", {"class_names": class_names})

# =========================
# Homework List
# =========================
@login_required
def homework_list(request):

    if hasattr(request.user, 'student'):
        class_name = request.user.student.class_name
        homeworks = Homework.objects.select_related("teacher__user").filter(
            class_name=class_name
        ).order_by("-date_assigned")
    elif hasattr(request.user, 'teacher'):
        class_names = list(request.user.teacher.classes.values_list('name', flat=True))
        if class_names:
            homeworks = Homework.objects.select_related("teacher__user").filter(
                class_name__in=class_names
            ).order_by("-date_assigned")
        else:
            homeworks = Homework.objects.none()
    else:
        homeworks = Homework.objects.select_related("teacher__user").all().order_by("-date_assigned")

    context = {
        "homeworks": homeworks
    }

    return render(request, "homework/homework_list.html", context)


@login_required
def download_homework(request, homework_id):
    homework = get_object_or_404(Homework, id=homework_id)

    if not homework.file:
        raise Http404("Homework file not found.")

    if hasattr(request.user, "student"):
        if request.user.student.class_name != homework.class_name:
            return HttpResponseForbidden("You are not allowed to access this file.")
    elif hasattr(request.user, "teacher"):
        class_names = list(request.user.teacher.classes.values_list("name", flat=True))
        if homework.class_name not in class_names:
            return HttpResponseForbidden("You are not allowed to access this file.")
    elif getattr(request.user, "role", None) != "ADMIN" and not getattr(request.user, "is_superuser", False):
        return HttpResponseForbidden("You are not allowed to access this file.")

    filename = os.path.basename(homework.file.name)
    return FileResponse(homework.file.open("rb"), as_attachment=True, filename=filename)
