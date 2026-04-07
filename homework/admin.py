from django.contrib import admin
from .models import (
    Homework,
    Assignment,
    AssignmentSubmission,
    Quiz,
    Question,
    StudentQuizAttempt,
    Answer,
)

admin.site.register(Homework)


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("title", "class_assigned", "subject", "teacher", "due_date", "created_at")
    search_fields = ("title", "class_assigned__name", "subject", "teacher__username")
    list_filter = ("class_assigned", "subject")


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ("assignment", "student", "status", "submitted_at")
    search_fields = ("assignment__title", "student__username")
    list_filter = ("status",)


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ("title", "class_assigned", "teacher", "total_marks", "time_limit", "created_at")
    search_fields = ("title", "class_assigned__name", "teacher__username")
    inlines = [QuestionInline]


@admin.register(StudentQuizAttempt)
class StudentQuizAttemptAdmin(admin.ModelAdmin):
    list_display = ("quiz", "student", "score", "submitted_at")
    search_fields = ("quiz__title", "student__username")


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ("attempt", "question", "selected_option")
    search_fields = ("attempt__student__username", "question__quiz__title")
