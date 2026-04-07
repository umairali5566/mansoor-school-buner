from django.conf import settings
from django.db import models
from django.utils import timezone

from accounts.models import Classroom, Teacher


class Homework(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    class_name = models.CharField(max_length=50)
    subject = models.CharField(max_length=100, default="General")
    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="homeworks",
    )
    file = models.FileField(upload_to="homework_files/", null=True, blank=True)
    date_assigned = models.DateField(auto_now_add=True)
    due_date = models.DateField(null=True, blank=True)
    notification_sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title


class Assignment(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    class_assigned = models.ForeignKey(
        Classroom,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    subject = models.CharField(max_length=100, blank=True, default="")
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignments_created",
    )
    file = models.FileField(upload_to="assignment_files/", null=True, blank=True)
    due_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.title


class AssignmentSubmission(models.Model):
    STATUS_CHOICES = (
        ("Submitted", "Submitted"),
        ("Late", "Late"),
        ("Pending", "Pending"),
    )

    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assignment_submissions",
    )
    file = models.FileField(upload_to="assignment_submissions/")
    submitted_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")

    class Meta:
        unique_together = ("assignment", "student")
        ordering = ("-submitted_at",)

    def save(self, *args, **kwargs):
        if self.file:
            if self.assignment_id and self.submitted_at > self.assignment.due_date:
                self.status = "Late"
            else:
                self.status = "Submitted"
        else:
            self.status = "Pending"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.assignment.title} - {self.student.username}"


class Quiz(models.Model):
    title = models.CharField(max_length=200)
    class_assigned = models.ForeignKey(
        Classroom,
        on_delete=models.CASCADE,
        related_name="quizzes",
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quizzes_created",
    )
    total_marks = models.PositiveIntegerField(default=0)
    time_limit = models.PositiveIntegerField(default=15, help_text="Time limit in minutes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.title

    @property
    def question_count(self):
        return self.questions.count()


class Question(models.Model):
    OPTION_CHOICES = (
        ("A", "Option A"),
        ("B", "Option B"),
        ("C", "Option C"),
        ("D", "Option D"),
    )

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    question_text = models.TextField()
    option_a = models.CharField(max_length=255)
    option_b = models.CharField(max_length=255)
    option_c = models.CharField(max_length=255)
    option_d = models.CharField(max_length=255)
    correct_answer = models.CharField(max_length=1, choices=OPTION_CHOICES)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ("order", "id")

    def __str__(self):
        return f"Q{self.order} - {self.quiz.title}"


class StudentQuizAttempt(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="quiz_attempts",
    )
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    score = models.PositiveIntegerField(default=0)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("student", "quiz")
        ordering = ("-submitted_at",)

    @property
    def percentage(self):
        if self.quiz.total_marks <= 0:
            return 0.0
        return round((self.score / self.quiz.total_marks) * 100, 1)

    def __str__(self):
        return f"{self.student.username} - {self.quiz.title}"


class Answer(models.Model):
    OPTION_CHOICES = (
        ("A", "Option A"),
        ("B", "Option B"),
        ("C", "Option C"),
        ("D", "Option D"),
    )

    attempt = models.ForeignKey(
        StudentQuizAttempt,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    selected_option = models.CharField(max_length=1, choices=OPTION_CHOICES, blank=True, default="")

    class Meta:
        unique_together = ("attempt", "question")

    def __str__(self):
        return f"{self.attempt.student.username} - Q{self.question.id}"
