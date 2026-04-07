from django.urls import path
from . import views

urlpatterns = [
    path("upload/", views.upload_homework, name="upload_homework"),
    path("list/", views.homework_list, name="homework_list"),
    path("<int:homework_id>/download/", views.download_homework, name="download_homework"),
    path("assignments/", views.assignment_list, name="assignment_list"),
    path("assignments/create/", views.assignment_create, name="assignment_create"),
    path("create_assignment/", views.assignment_create, name="create_assignment"),
    path("assignments/<int:assignment_id>/", views.assignment_detail, name="assignment_detail"),
    path("assignments/<int:assignment_id>/edit/", views.assignment_edit, name="assignment_edit"),
    path("assignments/<int:assignment_id>/delete/", views.assignment_delete, name="assignment_delete"),
    path("assignments/<int:assignment_id>/submit/", views.assignment_submit, name="assignment_submit"),
    path("assignments/<int:assignment_id>/download/", views.download_assignment_file, name="download_assignment_file"),
    path(
        "assignments/submission/<int:submission_id>/download/",
        views.download_assignment_submission,
        name="download_assignment_submission",
    ),
    path("quizzes/", views.quiz_list, name="quiz_list"),
    path("quizzes/create/", views.quiz_create, name="quiz_create"),
    path("create_quiz/", views.quiz_create, name="create_quiz"),
    path("quizzes/<int:quiz_id>/edit/", views.quiz_edit, name="quiz_edit"),
    path("quizzes/<int:quiz_id>/delete/", views.quiz_delete, name="quiz_delete"),
    path("quizzes/<int:quiz_id>/questions/", views.quiz_manage_questions, name="quiz_manage_questions"),
    path(
        "quizzes/<int:quiz_id>/questions/<int:question_id>/delete/",
        views.quiz_delete_question,
        name="quiz_delete_question",
    ),
    path("quizzes/<int:quiz_id>/start/", views.quiz_start, name="quiz_start"),
    path("quizzes/<int:quiz_id>/result/", views.quiz_result, name="quiz_result"),
    path("quizzes/<int:quiz_id>/analytics/", views.quiz_analytics, name="quiz_analytics"),
]
