from django.urls import path
from . import views

urlpatterns = [

    # =============================
    # Manual Attendance
    # =============================
    path("mark/", views.mark_attendance, name="mark_attendance"),

    # =============================
    # Attendance Report
    # =============================
    path("report/", views.attendance_report, name="attendance_report"),

    # =============================
    # Student Self Attendance
    # =============================
    path("my-attendance/", views.student_attendance, name="student_attendance"),

    # =============================
    # Upload Face Dataset
    # =============================
    path("upload-face/<int:student_id>/", views.upload_face, name="upload_face"),

    # =============================
    # Simple Face Attendance
    # =============================
    path("face-attendance/", views.face_attendance, name="face_attendance"),

    # =============================
    # Single Face Capture
    # =============================
    path("mark-face/", views.mark_attendance_by_face, name="mark_face_attendance"),

    # =============================
    # Live Multi Camera Page
    # =============================
    path("live-attendance/", views.live_attendance_page, name="live_attendance"),

    # =============================
    # Camera Streaming
    # =============================
    path("start-video-feed/<int:camera_id>/", views.start_camera_feed, name="start_camera_feed"),
    path("stop-video-feeds/", views.stop_camera_feeds, name="stop_camera_feeds"),
    path("video-feed/<int:camera_id>/", views.video_feed, name="video_feed"),

    # =============================
    # Live Attendance Messages
    # =============================
    path("live-messages/", views.live_messages, name="live_messages"),

    # =============================
    # Attendance Analytics
    # =============================
    path("analytics/", views.attendance_analytics, name="attendance_analytics"),

    # =============================
    # Unknown Faces
    # =============================
    path("unknown-faces/", views.unknown_faces_list, name="unknown_faces_list"),

    # Convert unknown face to student
    path(
        "convert-unknown/<int:face_id>/",
        views.convert_unknown_to_student,
        name="convert_unknown"
    ),
    path(
        "delete-unknown/<int:face_id>/",
        views.delete_unknown_face,
        name="delete_unknown_face"
    ),

    path('test-email/', views.test_email, name='test_email'),
    path('edit-attendance/<int:id>/', views.edit_attendance, name='edit_attendance'),

]
