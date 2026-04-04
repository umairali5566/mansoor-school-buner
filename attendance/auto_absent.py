from datetime import date as dt_date
from datetime import time as dt_time
import logging

from django.utils import timezone
from django.utils.timezone import localtime

from accounts.models import Student
from .models import Attendance
from .services import save_attendance_record
from .utils import send_attendance_notification


ABSENCE_CUTOFF_TIME = dt_time(10, 2)
LOGGER = logging.getLogger(__name__)


def mark_auto_absent(target_date=None, force=False):
    """
    Mark Absent for students who still have no attendance record.
    Idempotent: safe to run multiple times per day.
    """
    now_local = localtime()
    run_date = target_date or now_local.date()

    if not isinstance(run_date, dt_date):
        raise ValueError("target_date must be a date instance or None")

    if target_date is None and not force and now_local.time() < ABSENCE_CUTOFF_TIME:
        return {
            "ran": False,
            "date": run_date,
            "reason": "before_cutoff",
            "cutoff": ABSENCE_CUTOFF_TIME,
            "created_absent": 0,
            "total_students": Student.objects.count(),
        }

    students = list(Student.objects.select_related("user").all())
    student_ids = [student.id for student in students]
    marked_ids = set(
        Attendance.objects.filter(date=run_date).values_list("student_id", flat=True)
    )
    missing_students = [student for student in students if student.id not in marked_ids]

    created_absent = 0
    for student in missing_students:
        _, created, _ = save_attendance_record(
            student=student,
            status="Absent",
            marked_by="AUTO_ABSENT",
            attendance_date=run_date,
            marked_at=timezone.now(),
            overwrite_existing=False,
        )
        if created:
            created_absent += 1

    emails_sent = 0
    if missing_students:
        missing_ids = [student.id for student in missing_students]
        created_absent_rows = Attendance.objects.select_related("student__user").filter(
            date=run_date,
            status="Absent",
            student_id__in=missing_ids,
        )

        # Signals may already send emails on create; count those first.
        emails_sent += created_absent_rows.exclude(notification_sent_at__isnull=True).count()

        for attendance in created_absent_rows.filter(notification_sent_at__isnull=True):
            if send_attendance_notification(attendance):
                emails_sent += 1

    marked_count = Attendance.objects.filter(date=run_date).values("student_id").distinct().count()
    present_count = Attendance.objects.filter(date=run_date, status="Present").count()
    absent_count = Attendance.objects.filter(date=run_date, status="Absent").count()

    LOGGER.info(
        "Auto absent run: date=%s force=%s total_students=%s marked_before=%s created_absent=%s emails_sent=%s marked_after=%s present=%s absent=%s",
        run_date,
        force,
        len(student_ids),
        len(marked_ids),
        created_absent,
        emails_sent,
        marked_count,
        present_count,
        absent_count,
    )

    return {
        "ran": True,
        "date": run_date,
        "created_absent": created_absent,
        "emails_sent": emails_sent,
        "total_students": len(student_ids),
        "present_count": present_count,
        "absent_count": absent_count,
        "marked_count": marked_count,
    }
