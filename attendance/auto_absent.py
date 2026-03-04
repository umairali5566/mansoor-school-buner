from datetime import date
from accounts.models import Student
from .models import Attendance


def mark_auto_absent():

    today = date.today()

    students = Student.objects.all()

    for student in students:

        already_marked = Attendance.objects.filter(
            student=student,
            date=today
        ).exists()

        if not already_marked:

            Attendance.objects.create(
                student=student,
                date=today,
                status="Absent"
            )

    print("Auto Absent marked successfully")