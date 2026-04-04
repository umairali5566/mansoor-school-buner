from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Attendance
from .utils import send_attendance_notification


@receiver(post_save, sender=Attendance)
def attendance_notification_on_create(sender, instance, created, **kwargs):
    """
    Send attendance email once for a new attendance record.
    If a record exists without notification metadata, allow one recovery send
    when status is saved.
    """
    update_fields = kwargs.get("update_fields")
    status_touched = update_fields is None or "status" in update_fields

    should_send = created or (
        instance.notification_sent_at is None and status_touched
    )

    if should_send:
        send_attendance_notification(instance)
