from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [

    # =====================================================
    # AUTH
    # =====================================================
    path('', views.login_view, name='login'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),


    # =====================================================
    # DASHBOARDS
    # =====================================================
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('teacher-dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher-classes/', views.teacher_classes, name='teacher_classes'),
    path('student-dashboard/', views.student_dashboard, name='student_dashboard'),


    # =====================================================
    # STUDENT MANAGEMENT (ADMIN)
    # =====================================================
    path('students/', views.student_list, name='student_list'),
    path('student-admissions/', views.student_admissions, name='student_admissions'),
    path('add-student/', views.add_student, name='add_student'),
    path('student-admissions/add/', views.add_student, name='add_student_admission'),
    path('edit-student/<int:student_id>/', views.edit_student, name='edit_student'),
    path('student-admissions/<int:student_id>/edit/', views.edit_student, name='edit_student_admission'),
    path('delete-student/<int:student_id>/', views.delete_student, name='delete_student'),
    path('reset-student-password/<int:student_id>/', 
         views.reset_student_password, 
         name='reset_student_password'),


    # =====================================================
    # TEACHER MANAGEMENT (ADMIN)
    # =====================================================
    path('teachers/', views.teacher_list, name='teacher_list'),
    path('add-teacher/', views.add_teacher, name='add_teacher'),
    path('assign-teacher-classes/<int:teacher_id>/', views.assign_teacher_classes, name='assign_teacher_classes'),
    path('edit-teacher/<int:teacher_id>/', views.edit_teacher, name='edit_teacher'),
    path('delete-teacher/<int:teacher_id>/', views.delete_teacher, name='delete_teacher'),
    path('reset-teacher-password/<int:teacher_id>/', 
         views.reset_teacher_password, 
         name='reset_teacher_password'),


    # =====================================================
    # STUDENT PROFILE
    # =====================================================

    path('student-profile/<int:id>/', views.student_profile, name='student_profile'),

    # =====================================================
    # CHANGE PASSWORD (BUILT-IN DJANGO)
    # =====================================================
    path('change-password/',
         auth_views.PasswordChangeView.as_view(
             template_name='accounts/change_password.html'
         ),
         name='change_password'),

    path('change-password-done/',
         auth_views.PasswordChangeDoneView.as_view(
             template_name='accounts/change_password_done.html'
         ),
         name='password_change_done'),

    # password reset using built-in views
    path('password-reset/',
         auth_views.PasswordResetView.as_view(
             template_name='accounts/password_reset.html',
             email_template_name='accounts/password_reset_email.html',
             subject_template_name='accounts/password_reset_subject.txt',
         ),
         name='password_reset'),
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='accounts/password_reset_done.html'
         ),
         name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='accounts/password_reset_confirm.html'
         ),
         name='password_reset_confirm'),
    path('password-reset-complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='accounts/password_reset_complete.html'
         ),
         name='password_reset_complete'),


    path("edit-student-profile/<int:student_id>/", views.edit_student_profile, name="edit_student_profile"),
    path("teacher/add-student/", views.teacher_add_student, name="teacher_add_student"),

    # =====================================================
    # VIEW STUDENTS
    # =====================================================
    path('view-students/', views.view_students, name='view_students'),
]
