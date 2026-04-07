from django.urls import path

from . import views


urlpatterns = [
    path("", views.notification_center, name="notification_center"),
    path("mark-read/<int:notification_id>/", views.mark_notification_read, name="mark_notification_read"),
    path("mark-all-read/", views.mark_all_notifications_read, name="mark_all_notifications_read"),
]
