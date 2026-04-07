import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import localtime


LOGGER = logging.getLogger(__name__)
ABSENCE_CUTOFF_LABEL = "10:02 AM"


def _attendance_email_content(attendance):
    student = attendance.student
    student_name = student.user.get_full_name() or student.user.username
    roll_number = student.roll_number or "-"
    class_name = student.class_name or "-"
    status = attendance.status
    attendance_date = attendance.date
    marked_by = (getattr(attendance, "marked_by", "") or "SYSTEM").upper()
    marked_at = getattr(attendance, "marked_at", None) or timezone.now()
    marked_at_local = localtime(marked_at)
    marked_time_text = marked_at_local.strftime("%I:%M %p")
    attendance_date_text = attendance_date.strftime("%B %d, %Y")

    if status == "Present" and marked_by == "FACE":
        return (
            "Student Marked Present",
            (
                "Dear Parent,\n\n"
                f"Your child {student_name} (Roll No: {roll_number}, Class: {class_name}) "
                "has been marked Present via the school attendance system "
                f"at {marked_time_text} on {attendance_date_text}.\n\n"
                "School Management System"
            ),
        )

    if status == "Absent" and marked_by == "AUTO_ABSENT":
        return (
            "Student Marked Absent",
            (
                "Dear Parent,\n\n"
                f"Your child {student_name} (Roll No: {roll_number}, Class: {class_name}) "
                f"was marked Absent today because attendance was not recorded before {ABSENCE_CUTOFF_LABEL}.\n\n"
                f"Date: {attendance_date_text}\n\n"
                "School Management System"
            ),
        )

    return (
        "Student Attendance Notification",
        (
            "Dear Parent,\n\n"
            f"This is to inform you that your child {student_name} "
            f"(Roll No: {roll_number}, Class: {class_name}) has been marked "
            f"{status} on {attendance_date_text}.\n\n"
            "Thank you.\n\n"
            "School Management System"
        ),
    )


def send_attendance_notification(attendance, force=False):
    """
    Send one attendance notification email per attendance record.
    Returns True when an email is sent successfully, otherwise False.
    """
    if attendance is None or getattr(attendance, "student_id", None) is None:
        return False

    student = attendance.student
    parent_email = (student.parent_email or "").strip()
    if not parent_email:
        return False

    already_sent = bool(getattr(attendance, "notification_sent_at", None))
    if already_sent and not force:
        return False

    subject, message = _attendance_email_content(attendance)
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or settings.EMAIL_HOST_USER

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[parent_email],
            fail_silently=False,
        )
    except Exception:
        LOGGER.exception(
            "Failed to send attendance email. attendance_id=%s student_id=%s status=%s date=%s",
            attendance.id,
            student.id,
            attendance.status,
            attendance.date,
        )
        return False

    attendance.notification_sent_at = timezone.now()
    attendance.notification_status = attendance.status
    attendance.save(update_fields=["notification_sent_at", "notification_status"])

    # In-app alert for the student portal.
    try:
        from notifications.models import Notification
        from notifications.services import create_notification

        student_user = getattr(student, "user", None)
        if student_user and student_user.is_active:
            create_notification(
                user=student_user,
                title=f"Attendance marked: {attendance.status}",
                message=f"Your attendance for {attendance.date.strftime('%b %d, %Y')} was marked as {attendance.status}.",
                notification_type=Notification.TYPE_ATTENDANCE,
                link_url=reverse("student_attendance"),
                metadata={
                    "attendance_id": attendance.id,
                    "status": attendance.status,
                    "date": attendance.date.isoformat(),
                },
            )
    except Exception:
        LOGGER.exception("Failed to create in-app attendance notification. attendance_id=%s", attendance.id)

    return True


def send_attendance_email(student_email, student_name, status):
    """
    Backward-compatible helper used by old test hooks.
    """
    if not student_email:
        return False

    subject = "Student Attendance Notification"
    message = (
        "Dear Parent,\n\n"
        f"This is to inform you that your child {student_name} has been marked "
        f"{status}.\n\n"
        "Thank you.\n\n"
        "School Management System"
    )
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or settings.EMAIL_HOST_USER

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[student_email],
            fail_silently=False,
        )
    except Exception:
        LOGGER.exception(
            "Failed to send legacy attendance email to %s for student=%s",
            student_email,
            student_name,
        )
        return False

    return True
