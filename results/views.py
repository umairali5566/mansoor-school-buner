from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Result
from accounts.models import Student

@login_required
def add_result(request):
    if not hasattr(request.user, 'teacher'):
        return redirect('teacher_dashboard')

    teacher = request.user.teacher
    class_names = list(teacher.classes.values_list('name', flat=True))
    students = Student.objects.filter(class_name__in=class_names)

    if request.method == 'POST':
        student_id = request.POST.get('student')
        subject = request.POST.get('subject')
        marks = request.POST.get('marks')
        total_marks = request.POST.get('total_marks', 100)
        exam_type = request.POST.get('exam_type')

        student = get_object_or_404(Student, id=student_id, class_name__in=class_names)

        Result.objects.create(
            student=student,
            subject=subject,
            marks=int(marks),
            total_marks=int(total_marks),
            exam_type=exam_type
        )

        messages.success(request, 'Result added successfully.')
        return redirect('teacher_dashboard')

    return render(request, 'results/add_result.html', {'students': students})

@login_required
def result_list(request):
    if hasattr(request.user, 'student'):
        results = Result.objects.filter(student=request.user.student)
    elif hasattr(request.user, 'teacher'):
        class_names = list(request.user.teacher.classes.values_list('name', flat=True))
        results = Result.objects.filter(student__class_name__in=class_names)
    else:
        results = Result.objects.all()

    return render(request, 'results/result_list.html', {'results': results})
