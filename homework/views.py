from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Homework


# =========================
# Upload Homework (Teacher)
# =========================
@login_required
def upload_homework(request):

    if request.method == "POST":

        title = request.POST.get("title")
        description = request.POST.get("description")
        class_name = request.POST.get("class_name")

        file = request.FILES.get("file")

        Homework.objects.create(
            title=title,
            description=description,
            class_name=class_name,
            file=file
        )

        return redirect("teacher_dashboard")

    return render(request, "homework/upload_homework.html")

# =========================
# Homework List
# =========================
@login_required
def homework_list(request):

    homeworks = Homework.objects.all().order_by("-date_assigned")

    context = {
        "homeworks": homeworks
    }

    return render(request, "homework/homework_list.html", context)