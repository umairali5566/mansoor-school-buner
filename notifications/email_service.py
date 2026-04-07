import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser, Student
from notifications.models import Notification
from notifications.services import create_notification, create_notifications_for_users


LOGGER = logging.getLogger(__name__)


def _from_email():
    return getattr(settings, "DEFAULT_FROM_EMAIL", None) or settings.EMAIL_HOST_USER


def _clean_email(value):
    return (value or "").strip()


def send_homework_notification(homework, force=False):
    """
    Notify all parents of students in the homework class.
    Returns the number of recipients successfully targeted.
    """
    if homework is None or getattr(homework, "id", None) is None:
        return 0

    if getattr(homework, "notification_sent_at", None) and not force:
        return 0

    recipients = []
    seen = set()
    for email in Student.objects.filter(class_name=homework.class_name).values_list("parent_email", flat=True):
        cleaned = _clean_email(email)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        recipients.append(cleaned)

    if not recipients:
        return 0

    date_text = homework.date_assigned.strftime("%B %d, %Y")
    subject = "New Homework Assigned"
    message = (
        "Dear Parent,\n\n"
        "New homework has been assigned to your child's class.\n\n"
        f"Class: {homework.class_name}\n"
        f"Subject: {homework.subject}\n"
        f"Homework: {homework.title}\n"
        f"Date: {date_text}\n"
    )

    if homework.description:
        message += f"Description: {homework.description}\n"
    if homework.due_date:
        message += f"Due Date: {homework.due_date.strftime('%B %d, %Y')}\n"

    message += "\nPlease ask your child to complete the assignment.\n\nSchool Management System"

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=_from_email(),
            recipient_list=recipients,
            fail_silently=False,
        )
    except Exception:
        LOGGER.exception("Failed homework notification for homework_id=%s", homework.id)
        return 0

    homework.notification_sent_at = timezone.now()
    homework.save(update_fields=["notification_sent_at"])

    # Create in-app notifications for class students and administrators.
    student_users = [
        student.user
        for student in Student.objects.select_related("user").filter(class_name=homework.class_name)
        if getattr(student, "user", None) and student.user.is_active
    ]
    create_notifications_for_users(
        users=student_users,
        title=f"New homework: {homework.title}",
        message=f"{homework.subject} homework was posted for class {homework.class_name}.",
        notification_type=Notification.TYPE_HOMEWORK,
        link_url=reverse("homework_list"),
        metadata={"homework_id": homework.id, "class_name": homework.class_name},
    )

    admin_users = CustomUser.objects.filter(role="ADMIN", is_active=True)
    create_notifications_for_users(
        users=admin_users,
        title="Homework published",
        message=f"{homework.subject} homework was published for class {homework.class_name}.",
        notification_type=Notification.TYPE_HOMEWORK,
        link_url=reverse("homework_list"),
        metadata={"homework_id": homework.id, "class_name": homework.class_name},
    )
    return len(recipients)


def send_result_notification(result, force=False):
    """
    Notify the specific parent when a result is uploaded.
    Returns True on success, False otherwise.
    """
    if result is None or getattr(result, "id", None) is None:
        return False

    if getattr(result, "notification_sent_at", None) and not force:
        return False

    student = result.student
    recipient = _clean_email(getattr(student, "parent_email", None))
    if not recipient:
        return False

    student_name = student.user.get_full_name() or student.user.username
    date_text = result.date.strftime("%B %d, %Y")

    subject = "New Result Uploaded"
    message = (
        "Dear Parent,\n\n"
        f"The exam result for your child {student_name} has been uploaded.\n\n"
        f"Subject: {result.subject}\n"
        f"Marks / Grade: {result.marks}/{result.total_marks}\n"
        f"Exam: {result.exam_type}\n"
        f"Date: {date_text}\n\n"
        "Please check the student portal for details.\n\n"
        "School Management System"
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=_from_email(),
            recipient_list=[recipient],
            fail_silently=False,
        )
    except Exception:
        LOGGER.exception("Failed result notification for result_id=%s", result.id)
        return False

    result.notification_sent_at = timezone.now()
    result.save(update_fields=["notification_sent_at"])

    student_user = getattr(student, "user", None)
    if student_user and student_user.is_active:
        create_notification(
            user=student_user,
            title=f"New result: {result.subject}",
            message=f"{result.exam_type} result has been published ({result.marks}/{result.total_marks}).",
            notification_type=Notification.TYPE_RESULT,
            link_url=reverse("result_list"),
            metadata={"result_id": result.id},
        )

    return True
