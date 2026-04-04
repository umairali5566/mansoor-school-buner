import logging

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.timezone import localdate

from .models import Attendance


LOGGER = logging.getLogger(__name__)
VALID_STATUSES = {"Present", "Absent"}


def save_attendance_record(
    student,
    status,
    marked_by="SYSTEM",
    attendance_date=None,
    marked_at=None,
    overwrite_existing=True,
):
    """
    Centralized attendance save/update helper used by all attendance sources.
    Returns: (attendance, created, updated)
    """
    if student is None:
        raise ValueError("student is required")

    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid attendance status: {status}")

    attendance_date = attendance_date or localdate()
    marked_at = marked_at or timezone.now()
    student_class = (getattr(student, "class_name", "") or "").strip()

    for _ in range(2):
        try:
            with transaction.atomic():
                attendance = (
                    Attendance.objects.select_for_update()
                    .filter(student=student, date=attendance_date)
                    .first()
                )

                if attendance is None:
                    attendance = Attendance.objects.create(
                        student=student,
                        student_class=student_class,
                        date=attendance_date,
                        status=status,
                        marked_by=marked_by,
                        marked_at=marked_at,
                    )
                    LOGGER.info(
                        "Attendance saved: student_id=%s class=%s date=%s status=%s marked_by=%s created=True updated=False",
                        student.id,
                        student_class,
                        attendance_date,
                        status,
                        marked_by,
                    )
                    return attendance, True, False

                if not overwrite_existing:
                    LOGGER.info(
                        "Attendance unchanged: student_id=%s class=%s date=%s status=%s marked_by=%s created=False updated=False",
                        student.id,
                        student_class or attendance.student_class,
                        attendance_date,
                        attendance.status,
                        attendance.marked_by,
                    )
                    return attendance, False, False

                changed = (
                    attendance.status != status
                    or attendance.marked_by != marked_by
                    or attendance.student_class != student_class
                )

                if changed:
                    attendance.status = status
                    attendance.marked_by = marked_by
                    attendance.marked_at = marked_at
                    attendance.student_class = student_class
                    attendance.save(
                        update_fields=["status", "marked_by", "marked_at", "student_class"]
                    )

                LOGGER.info(
                    "Attendance saved: student_id=%s class=%s date=%s status=%s marked_by=%s created=False updated=%s",
                    student.id,
                    student_class,
                    attendance_date,
                    status,
                    marked_by,
                    changed,
                )
                return attendance, False, changed
        except IntegrityError:
            LOGGER.warning(
                "Attendance save race condition. Retrying student_id=%s date=%s",
                getattr(student, "id", None),
                attendance_date,
            )

    attendance = Attendance.objects.get(student=student, date=attendance_date)
    if not overwrite_existing:
        return attendance, False, False

    changed = (
        attendance.status != status
        or attendance.marked_by != marked_by
        or attendance.student_class != student_class
    )
    if changed:
        attendance.status = status
        attendance.marked_by = marked_by
        attendance.marked_at = marked_at
        attendance.student_class = student_class
        attendance.save(update_fields=["status", "marked_by", "marked_at", "student_class"])
    return attendance, False, changed
