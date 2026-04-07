import os
import logging
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Prefetch, Q
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from accounts.models import Classroom, Student
from .forms import AssignmentForm, AssignmentSubmissionForm, QuestionForm, QuizForm
from .models import (
    Answer,
    Assignment,
    AssignmentSubmission,
    Homework,
    Question,
    Quiz,
    StudentQuizAttempt,
)

LOGGER = logging.getLogger(__name__)


def _is_admin(user):
    return getattr(user, "role", "") == "ADMIN" or getattr(user, "is_superuser", False)


def _is_teacher(user):
    return getattr(user, "role", "") == "TEACHER" and hasattr(user, "teacher")


def _is_student(user):
    return getattr(user, "role", "") == "STUDENT" and hasattr(user, "student")


def _allowed_classrooms_for_user(user):
    if _is_teacher(user):
        return user.teacher.classes.order_by("name")
    return Classroom.objects.none()


def _status_badge(status):
    if status == "Submitted":
        return "status-badge-success"
    if status == "Late":
        return "status-badge-warning"
    return "status-badge-danger"


def _assignment_status_for_student(assignment, submission, *, now):
    if submission is not None:
        return submission.status, _status_badge(submission.status)
    if assignment.due_date < now:
        return "Late", _status_badge("Late")
    return "Pending", _status_badge("Pending")


def _can_manage_assignment(user, assignment):
    if not _is_teacher(user):
        return False
    allowed_class_ids = set(user.teacher.classes.values_list("id", flat=True))
    return assignment.class_assigned_id in allowed_class_ids and assignment.teacher_id == user.id


def _can_access_assignment(user, assignment):
    if _is_admin(user):
        return True
    if _is_teacher(user):
        return _can_manage_assignment(user, assignment)
    if _is_student(user):
        return user.student.class_name == assignment.class_assigned.name
    return False


def _can_manage_quiz(user, quiz):
    if not _is_teacher(user):
        return False
    allowed_class_ids = set(user.teacher.classes.values_list("id", flat=True))
    return quiz.class_assigned_id in allowed_class_ids and quiz.teacher_id == user.id


def _can_access_quiz(user, quiz):
    if _is_teacher(user):
        return _can_manage_quiz(user, quiz)
    if _is_student(user):
        return user.student.class_name == quiz.class_assigned.name
    return False


def _quiz_attempt_percentage(score, max_score):
    if max_score <= 0:
        return 0.0
    return round((score / max_score) * 100, 1)


# =========================
# Upload Homework (Teacher)
# =========================
@login_required
def upload_homework(request):
    if getattr(request.user, "role", "") != "TEACHER" or not _is_teacher(request.user):
        return HttpResponseForbidden("Only teachers allowed")

    teacher = request.user.teacher
    class_names = list(teacher.classes.values_list("name", flat=True))
    if not class_names:
        messages.error(request, "Cannot upload homework until your class is assigned.")
        return redirect("teacher_dashboard")

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
    if _is_student(request.user):
        class_name = request.user.student.class_name
        homeworks = Homework.objects.select_related("teacher__user").filter(class_name=class_name).order_by("-date_assigned")
    elif _is_teacher(request.user):
        class_names = list(request.user.teacher.classes.values_list("name", flat=True))
        if class_names:
            homeworks = Homework.objects.select_related("teacher__user").filter(class_name__in=class_names).order_by("-date_assigned")
        else:
            homeworks = Homework.objects.none()
    else:
        homeworks = Homework.objects.select_related("teacher__user").all().order_by("-date_assigned")

    return render(request, "homework/homework_list.html", {"homeworks": homeworks})


@login_required
def download_homework(request, homework_id):
    homework = get_object_or_404(Homework, id=homework_id)

    if not homework.file:
        raise Http404("Homework file not found.")

    if _is_student(request.user):
        if request.user.student.class_name != homework.class_name:
            return HttpResponseForbidden("You are not allowed to access this file.")
    elif _is_teacher(request.user):
        class_names = list(request.user.teacher.classes.values_list("name", flat=True))
        if homework.class_name not in class_names:
            return HttpResponseForbidden("You are not allowed to access this file.")
    elif not _is_admin(request.user):
        return HttpResponseForbidden("You are not allowed to access this file.")

    filename = os.path.basename(homework.file.name)
    return FileResponse(homework.file.open("rb"), as_attachment=True, filename=filename)


# ===================================
# Assignments - List / CRUD / Submit
# ===================================
@login_required
def assignment_list(request):
    role = getattr(request.user, "role", "")
    now = timezone.now()

    assignment_qs = Assignment.objects.select_related("class_assigned", "teacher").prefetch_related(
        Prefetch("submissions", queryset=AssignmentSubmission.objects.select_related("student"), to_attr="prefetched_submissions")
    )

    if _is_student(request.user):
        assignment_qs = assignment_qs.filter(class_assigned__name=request.user.student.class_name)
    elif _is_teacher(request.user):
        allowed_ids = list(_allowed_classrooms_for_user(request.user).values_list("id", flat=True))
        assignment_qs = assignment_qs.filter(
            teacher=request.user,
            class_assigned_id__in=allowed_ids,
        )
        LOGGER.debug(
            "Teacher assignment filter | teacher=%s classes=%s assignment_count=%s",
            request.user.username,
            allowed_ids,
            assignment_qs.count(),
        )

    class_student_counts = {
        item["class_name"]: item["count"]
        for item in Student.objects.values("class_name").annotate(count=Count("id"))
    }

    assignment_cards = []
    for assignment in assignment_qs.order_by("-created_at"):
        submissions = list(getattr(assignment, "prefetched_submissions", []))
        due_is_expired = assignment.due_date < now

        my_submission = None
        if _is_student(request.user):
            for submission in submissions:
                if submission.student_id == request.user.id:
                    my_submission = submission
                    break

        my_status, my_status_class = _assignment_status_for_student(
            assignment,
            my_submission,
            now=now,
        )

        submitted_count = sum(1 for item in submissions if item.status == "Submitted")
        late_count = sum(1 for item in submissions if item.status == "Late")
        total_students = class_student_counts.get(assignment.class_assigned.name, 0)
        pending_count = max(total_students - len(submissions), 0)

        assignment_cards.append(
            {
                "assignment": assignment,
                "is_expired": due_is_expired,
                "time_left": max((assignment.due_date - now).total_seconds(), 0),
                "my_submission": my_submission,
                "my_status": my_status,
                "my_status_class": my_status_class,
                "submitted_count": submitted_count,
                "late_count": late_count,
                "pending_count": pending_count,
                "total_students": total_students,
                "teacher_name": (
                    assignment.teacher.get_full_name() or assignment.teacher.username
                ) if assignment.teacher else "Unassigned",
            }
        )

    context = {
        "assignment_cards": assignment_cards,
        "role": role,
        "can_manage": _is_teacher(request.user),
        "can_view_detail": True,
        "is_teacher_view": _is_teacher(request.user),
        "is_student_view": _is_student(request.user),
        "is_admin_view": _is_admin(request.user),
        "total_assignments": len(assignment_cards),
    }
    return render(request, "homework/assignment_list.html", context)


@login_required
def assignment_create(request):
    if not _is_teacher(request.user):
        return HttpResponseForbidden("Only teachers are allowed to create assignments.")

    allowed_classes = _allowed_classrooms_for_user(request.user)
    if not allowed_classes.exists():
        messages.error(request, "No classes are available for assignment publishing.")
        return redirect("assignment_list")

    form = AssignmentForm(request.POST or None, request.FILES or None)
    form.fields["class_assigned"].queryset = allowed_classes

    if request.method == "POST" and form.is_valid():
        assignment = form.save(commit=False)
        assignment.teacher = request.user
        if assignment.class_assigned_id not in set(allowed_classes.values_list("id", flat=True)):
            messages.error(request, "You can only assign tasks to your own classes.")
        else:
            assignment.save()
            messages.success(request, "Assignment created successfully.")
            return redirect("assignment_list")

    return render(request, "homework/assignment_form.html", {"form": form, "is_edit": False})


@login_required
def assignment_edit(request, assignment_id):
    assignment = get_object_or_404(Assignment.objects.select_related("class_assigned"), id=assignment_id)
    if not _can_manage_assignment(request.user, assignment):
        return HttpResponseForbidden("You are not allowed to edit this assignment.")

    allowed_classes = _allowed_classrooms_for_user(request.user)
    form = AssignmentForm(request.POST or None, request.FILES or None, instance=assignment)
    if _is_teacher(request.user):
        form.fields["class_assigned"].queryset = allowed_classes

    if request.method == "POST" and form.is_valid():
        updated_assignment = form.save(commit=False)
        if updated_assignment.class_assigned_id not in set(allowed_classes.values_list("id", flat=True)):
            messages.error(request, "You can only assign tasks to your own classes.")
        else:
            updated_assignment.save()
            messages.success(request, "Assignment updated successfully.")
            return redirect("assignment_detail", assignment_id=assignment.id)

    return render(request, "homework/assignment_form.html", {"form": form, "assignment": assignment, "is_edit": True})


@login_required
def assignment_delete(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    if not _can_manage_assignment(request.user, assignment):
        return HttpResponseForbidden("You are not allowed to delete this assignment.")

    if request.method == "POST":
        assignment.delete()
        messages.success(request, "Assignment deleted successfully.")
        return redirect("assignment_list")
    return redirect("assignment_detail", assignment_id=assignment.id)


@login_required
def assignment_detail(request, assignment_id):
    assignment = get_object_or_404(
        Assignment.objects.select_related("class_assigned", "teacher").prefetch_related(
            Prefetch("submissions", queryset=AssignmentSubmission.objects.select_related("student"), to_attr="prefetched_submissions")
        ),
        id=assignment_id,
    )
    if not _can_access_assignment(request.user, assignment):
        return HttpResponseForbidden("You are not allowed to view this assignment.")

    submissions = list(getattr(assignment, "prefetched_submissions", []))
    now = timezone.now()
    is_expired = assignment.due_date < now

    my_submission = None
    if _is_student(request.user):
        for submission in submissions:
            if submission.student_id == request.user.id:
                my_submission = submission
                break

    submission_rows = []
    submitted_count = 0
    late_count = 0
    pending_count = 0
    total_students = 0

    if _is_admin(request.user) or _is_teacher(request.user):
        class_students = Student.objects.select_related("user").filter(class_name=assignment.class_assigned.name).order_by(
            "roll_number",
            "user__username",
        )
        total_students = class_students.count()
        submission_map = {submission.student_id: submission for submission in submissions}
        for student in class_students:
            submission = submission_map.get(student.user_id)
            if submission is None:
                status = "Pending"
                status_class = _status_badge(status)
                pending_count += 1
            else:
                status = submission.status
                status_class = _status_badge(status)
                if status == "Submitted":
                    submitted_count += 1
                elif status == "Late":
                    late_count += 1

            submission_rows.append(
                {
                    "student": student,
                    "submission": submission,
                    "status": status,
                    "status_class": status_class,
                }
            )

    context = {
        "assignment": assignment,
        "is_expired": is_expired,
        "my_submission": my_submission,
        "my_status": _assignment_status_for_student(assignment, my_submission, now=now)[0],
        "my_status_class": _assignment_status_for_student(assignment, my_submission, now=now)[1],
        "submission_form": AssignmentSubmissionForm(),
        "submission_rows": submission_rows,
        "submitted_count": submitted_count,
        "late_count": late_count,
        "pending_count": pending_count,
        "total_students": total_students,
        "can_manage": _can_manage_assignment(request.user, assignment),
        "is_teacher_view": _is_teacher(request.user),
        "is_student_view": _is_student(request.user),
        "is_admin_view": _is_admin(request.user),
        "teacher_name": (assignment.teacher.get_full_name() or assignment.teacher.username) if assignment.teacher else "Unassigned",
    }
    return render(request, "homework/assignment_detail.html", context)


@login_required
def assignment_submit(request, assignment_id):
    if not _is_student(request.user):
        return HttpResponseForbidden("Only students can submit assignments.")

    assignment = get_object_or_404(Assignment.objects.select_related("class_assigned"), id=assignment_id)
    if request.user.student.class_name != assignment.class_assigned.name:
        return HttpResponseForbidden("You cannot submit assignments outside your class.")

    if request.method == "POST":
        form = AssignmentSubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            submission, _ = AssignmentSubmission.objects.get_or_create(
                assignment=assignment,
                student=request.user,
            )
            old_file = submission.file if submission.file else None
            submission.file = form.cleaned_data["file"]
            submission.submitted_at = timezone.now()
            submission.save()
            if old_file and old_file.name != submission.file.name:
                old_file.delete(save=False)

            if submission.status == "Late":
                messages.warning(request, "Assignment submitted, but it is marked Late.")
            else:
                messages.success(request, "Assignment submitted successfully.")
        else:
            messages.error(request, "Please attach a valid file to submit.")

    return redirect("assignment_detail", assignment_id=assignment.id)


@login_required
def download_assignment_file(request, assignment_id):
    assignment = get_object_or_404(Assignment.objects.select_related("class_assigned"), id=assignment_id)
    if not assignment.file:
        raise Http404("Assignment file not found.")
    if not _can_access_assignment(request.user, assignment):
        return HttpResponseForbidden("You are not allowed to access this file.")
    filename = os.path.basename(assignment.file.name)
    return FileResponse(assignment.file.open("rb"), as_attachment=True, filename=filename)


@login_required
def download_assignment_submission(request, submission_id):
    submission = get_object_or_404(
        AssignmentSubmission.objects.select_related("assignment__class_assigned", "student"),
        id=submission_id,
    )
    if not submission.file:
        raise Http404("Submission file not found.")

    if _is_student(request.user):
        if submission.student_id != request.user.id:
            return HttpResponseForbidden("You are not allowed to access this submission.")
    elif _is_teacher(request.user):
        allowed_class_names = set(request.user.teacher.classes.values_list("name", flat=True))
        if submission.assignment.class_assigned.name not in allowed_class_names:
            return HttpResponseForbidden("You are not allowed to access this submission.")
    else:
        return HttpResponseForbidden("You are not allowed to access this submission.")

    filename = os.path.basename(submission.file.name)
    return FileResponse(submission.file.open("rb"), as_attachment=True, filename=filename)


# ==========================
# Quiz - List / CRUD / Play
# ==========================
@login_required
def quiz_list(request):
    quiz_qs = (
        Quiz.objects.select_related("class_assigned", "teacher")
        .annotate(question_total=Count("questions", distinct=True), attempt_total=Count("attempts", distinct=True))
        .order_by("-created_at")
    )

    if _is_student(request.user):
        quiz_qs = quiz_qs.filter(class_assigned__name=request.user.student.class_name)
        attempts_map = {
            attempt.quiz_id: attempt
            for attempt in StudentQuizAttempt.objects.filter(student=request.user, quiz__in=quiz_qs)
        }
    elif _is_teacher(request.user):
        class_ids = list(_allowed_classrooms_for_user(request.user).values_list("id", flat=True))
        quiz_qs = quiz_qs.filter(
            teacher=request.user,
            class_assigned_id__in=class_ids,
        )
        attempts_map = {}
        LOGGER.debug(
            "Teacher quiz filter | teacher=%s classes=%s quiz_count=%s",
            request.user.username,
            class_ids,
            quiz_qs.count(),
        )
    else:
        attempts_map = {}

    quizzes = []
    for quiz in quiz_qs:
        attempt = attempts_map.get(quiz.id)
        question_total = int(getattr(quiz, "question_total", 0) or 0)
        attempt_total = int(getattr(quiz, "attempt_total", 0) or 0)
        max_score = quiz.total_marks if quiz.total_marks > 0 else question_total
        quizzes.append(
            {
                "quiz": quiz,
                "attempt": attempt,
                "attempt_percentage": _quiz_attempt_percentage(attempt.score, max_score) if attempt else None,
                "max_score": max_score,
                "question_total": question_total,
                "attempt_total": attempt_total,
            }
        )

    return render(
        request,
        "homework/quiz_list.html",
        {
            "quizzes": quizzes,
            "can_manage": _is_teacher(request.user),
            "is_admin_view": _is_admin(request.user),
        },
    )


@login_required
def quiz_create(request):
    if not _is_teacher(request.user):
        return HttpResponseForbidden("Only teachers are allowed to create quizzes.")

    allowed_classes = _allowed_classrooms_for_user(request.user)
    if not allowed_classes.exists():
        messages.error(request, "No classes are available to create a quiz.")
        return redirect("quiz_list")

    form = QuizForm(request.POST or None)
    form.fields["class_assigned"].queryset = allowed_classes

    if request.method == "POST" and form.is_valid():
        quiz = form.save(commit=False)
        quiz.teacher = request.user
        if quiz.class_assigned_id not in set(allowed_classes.values_list("id", flat=True)):
            messages.error(request, "You can only create quizzes for your assigned classes.")
        else:
            quiz.save()
            messages.success(request, "Quiz created successfully. Add questions now.")
            return redirect("quiz_manage_questions", quiz_id=quiz.id)

    return render(request, "homework/quiz_form.html", {"form": form, "is_edit": False})


@login_required
def quiz_edit(request, quiz_id):
    quiz = get_object_or_404(Quiz.objects.select_related("class_assigned"), id=quiz_id)
    if not _can_manage_quiz(request.user, quiz):
        return HttpResponseForbidden("You are not allowed to edit this quiz.")

    form = QuizForm(request.POST or None, instance=quiz)
    if _is_teacher(request.user):
        form.fields["class_assigned"].queryset = _allowed_classrooms_for_user(request.user)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Quiz updated successfully.")
        return redirect("quiz_manage_questions", quiz_id=quiz.id)

    return render(request, "homework/quiz_form.html", {"form": form, "quiz": quiz, "is_edit": True})


@login_required
def quiz_delete(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    if not _can_manage_quiz(request.user, quiz):
        return HttpResponseForbidden("You are not allowed to delete this quiz.")

    if request.method == "POST":
        quiz.delete()
        messages.success(request, "Quiz deleted successfully.")
        return redirect("quiz_list")
    return redirect("quiz_list")


@login_required
def quiz_manage_questions(request, quiz_id):
    quiz = get_object_or_404(Quiz.objects.select_related("class_assigned"), id=quiz_id)
    if not _can_manage_quiz(request.user, quiz):
        return HttpResponseForbidden("You are not allowed to manage this quiz.")

    form = QuestionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        question = form.save(commit=False)
        question.quiz = quiz
        if question.order <= 0:
            question.order = quiz.questions.count() + 1
        question.save()
        question_count = quiz.questions.count()
        if quiz.total_marks < question_count:
            quiz.total_marks = question_count
            quiz.save(update_fields=["total_marks"])
        messages.success(request, "Question added successfully.")
        return redirect("quiz_manage_questions", quiz_id=quiz.id)

    questions = quiz.questions.all()
    return render(
        request,
        "homework/quiz_questions.html",
        {
            "quiz": quiz,
            "form": form,
            "questions": questions,
        },
    )


@login_required
def quiz_delete_question(request, quiz_id, question_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    if not _can_manage_quiz(request.user, quiz):
        return HttpResponseForbidden("You are not allowed to manage this quiz.")

    question = get_object_or_404(Question, id=question_id, quiz=quiz)
    if request.method == "POST":
        question.delete()
        messages.success(request, "Question removed.")
    return redirect("quiz_manage_questions", quiz_id=quiz.id)


@login_required
def quiz_start(request, quiz_id):
    if not _is_student(request.user):
        return HttpResponseForbidden("Only students can attempt quizzes.")

    quiz = get_object_or_404(Quiz.objects.select_related("class_assigned"), id=quiz_id)
    if not _can_access_quiz(request.user, quiz):
        return HttpResponseForbidden("You are not allowed to attempt this quiz.")

    existing_attempt = StudentQuizAttempt.objects.filter(student=request.user, quiz=quiz).first()
    if existing_attempt:
        messages.info(request, "You have already attempted this quiz.")
        return redirect("quiz_result", quiz_id=quiz.id)

    questions = list(quiz.questions.all())
    if not questions:
        messages.warning(request, "This quiz has no questions yet.")
        return redirect("quiz_list")

    session_key = f"quiz_start_{quiz.id}_{request.user.id}"
    if request.method == "GET":
        request.session[session_key] = timezone.now().isoformat()
        return render(request, "homework/quiz_start.html", {"quiz": quiz, "questions": questions})

    start_raw = request.session.get(session_key)
    if start_raw:
        started_at = parse_datetime(start_raw)
        if started_at is not None and timezone.is_naive(started_at):
            started_at = timezone.make_aware(started_at, timezone.get_current_timezone())
        if started_at is not None:
            elapsed_seconds = (timezone.now() - started_at).total_seconds()
            if elapsed_seconds > (quiz.time_limit * 60):
                messages.warning(request, "Quiz time limit was exceeded. Submission has been auto-evaluated.")

    attempt = StudentQuizAttempt.objects.create(student=request.user, quiz=quiz, score=0)
    score = 0
    answer_rows = []
    for question in questions:
        selected = (request.POST.get(f"question_{question.id}") or "").strip().upper()
        selected_option = selected if selected in {"A", "B", "C", "D"} else ""
        if selected_option == question.correct_answer:
            score += 1
        answer_rows.append(
            Answer(
                attempt=attempt,
                question=question,
                selected_option=selected_option,
            )
        )

    Answer.objects.bulk_create(answer_rows)
    attempt.score = score
    attempt.save(update_fields=["score"])
    if session_key in request.session:
        del request.session[session_key]

    messages.success(request, "Quiz submitted successfully.")
    return redirect("quiz_result", quiz_id=quiz.id)


@login_required
def quiz_result(request, quiz_id):
    quiz = get_object_or_404(Quiz.objects.select_related("class_assigned"), id=quiz_id)
    if not _can_access_quiz(request.user, quiz):
        return HttpResponseForbidden("You are not allowed to view this quiz result.")

    attempt = None
    if _is_student(request.user):
        attempt = StudentQuizAttempt.objects.filter(student=request.user, quiz=quiz).first()
    else:
        attempt_id = request.GET.get("attempt")
        if attempt_id:
            attempt = StudentQuizAttempt.objects.filter(id=attempt_id, quiz=quiz).select_related("student").first()

    if attempt is None:
        messages.warning(request, "Quiz result is not available yet.")
        return redirect("quiz_list")

    answers = list(attempt.answers.select_related("question").all())
    question_results = []
    for answer in answers:
        question = answer.question
        question_results.append(
            {
                "question": question,
                "selected_option": answer.selected_option,
                "correct_answer": question.correct_answer,
                "is_correct": answer.selected_option == question.correct_answer,
            }
        )

    max_score = quiz.total_marks if quiz.total_marks > 0 else quiz.questions.count()
    score_percentage = _quiz_attempt_percentage(attempt.score, max_score)

    return render(
        request,
        "homework/quiz_result.html",
        {
            "quiz": quiz,
            "attempt": attempt,
            "question_results": question_results,
            "max_score": max_score,
            "score_percentage": score_percentage,
        },
    )


@login_required
def quiz_analytics(request, quiz_id):
    quiz = get_object_or_404(Quiz.objects.select_related("class_assigned"), id=quiz_id)
    if not (_is_admin(request.user) or _is_teacher(request.user)):
        return HttpResponseForbidden("Only teacher/admin can view quiz analytics.")
    if _is_teacher(request.user) and not _can_manage_quiz(request.user, quiz):
        return HttpResponseForbidden("You are not allowed to view this quiz analytics.")

    attempts = StudentQuizAttempt.objects.filter(quiz=quiz).select_related("student").order_by("-score", "submitted_at")
    max_score = quiz.total_marks if quiz.total_marks > 0 else quiz.questions.count()

    analytics_rows = []
    for attempt in attempts:
        percentage = _quiz_attempt_percentage(attempt.score, max_score)
        if percentage > 75:
            badge = "status-badge-success"
            level = "Good"
        elif percentage >= 50:
            badge = "status-badge-warning"
            level = "Average"
        else:
            badge = "status-badge-danger"
            level = "Low"

        student_profile = Student.objects.filter(user=attempt.student).first()
        analytics_rows.append(
            {
                "attempt": attempt,
                "student_name": student_profile.display_name if student_profile else attempt.student.username,
                "class_name": student_profile.class_name if student_profile else quiz.class_assigned.name,
                "percentage": percentage,
                "level": level,
                "badge_class": badge,
            }
        )

    average_score = attempts.aggregate(avg_score=Avg("score")).get("avg_score") or 0
    average_percentage = _quiz_attempt_percentage(average_score, max_score) if max_score > 0 else 0
    top_performers = analytics_rows[:5]

    return render(
        request,
        "homework/quiz_analytics.html",
        {
            "quiz": quiz,
            "analytics_rows": analytics_rows,
            "max_score": max_score,
            "average_percentage": round(average_percentage, 1),
            "top_performers": top_performers,
            "attempt_count": attempts.count(),
        },
    )
