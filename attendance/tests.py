from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.timezone import localdate
from datetime import timedelta
import calendar

from accounts.models import Classroom, CustomUser, Student, Teacher
from attendance.auto_absent import mark_auto_absent
from attendance.models import Attendance


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AttendanceEmailNotificationTests(TestCase):
    def setUp(self):
        self.student_user = CustomUser.objects.create_user(
            username="student1",
            password="123456",
            role="STUDENT",
            first_name="Ali",
            last_name="Khan",
        )
        self.student = Student.objects.create(
            user=self.student_user,
            roll_number="A-12",
            class_name="10th-A",
            phone="03001234567",
            parent_email="parent@example.com",
        )

    def test_present_attendance_sends_email(self):
        attendance = Attendance.objects.create(
            student=self.student,
            date=localdate(),
            status="Present",
        )

        attendance.refresh_from_db()
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]

        self.assertIn("Student Attendance Notification", email.subject)
        self.assertIn("Ali Khan", email.body)
        self.assertIn("Roll No: A-12", email.body)
        self.assertIn("Class: 10th-A", email.body)
        self.assertIn("Present", email.body)
        self.assertIn(attendance.date.strftime("%B %d, %Y"), email.body)
        self.assertIsNotNone(attendance.notification_sent_at)
        self.assertEqual(attendance.notification_status, "Present")

    def test_absent_attendance_sends_email(self):
        attendance = Attendance.objects.create(
            student=self.student,
            date=localdate(),
            status="Absent",
        )

        attendance.refresh_from_db()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Absent", mail.outbox[0].body)
        self.assertEqual(attendance.notification_status, "Absent")

    def test_no_duplicate_email_for_same_record(self):
        attendance = Attendance.objects.create(
            student=self.student,
            date=localdate(),
            status="Present",
        )
        self.assertEqual(len(mail.outbox), 1)

        attendance.status = "Present"
        attendance.save()

        self.assertEqual(len(mail.outbox), 1)

    def test_no_email_when_parent_email_missing(self):
        self.student.parent_email = ""
        self.student.save(update_fields=["parent_email"])

        attendance = Attendance.objects.create(
            student=self.student,
            date=localdate(),
            status="Present",
        )

        attendance.refresh_from_db()
        self.assertEqual(len(mail.outbox), 0)
        self.assertIsNone(attendance.notification_sent_at)

    def test_auto_absent_sends_email_once(self):
        result = mark_auto_absent(target_date=localdate(), force=True)
        self.assertTrue(result["ran"])
        self.assertEqual(result["created_absent"], 1)
        self.assertEqual(result["emails_sent"], 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Student Marked Absent", mail.outbox[0].subject)
        self.assertIn("10:02 AM", mail.outbox[0].body)

        # second run should not create new rows or resend email
        result_second = mark_auto_absent(target_date=localdate(), force=True)
        self.assertTrue(result_second["ran"])
        self.assertEqual(result_second["created_absent"], 0)
        self.assertEqual(result_second["emails_sent"], 0)
        self.assertEqual(len(mail.outbox), 1)

    def test_face_present_email_uses_real_time_subject(self):
        Attendance.objects.create(
            student=self.student,
            date=localdate(),
            status="Present",
            marked_by="FACE",
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Student Marked Present", mail.outbox[0].subject)
        self.assertIn("has been marked Present via the school attendance system", mail.outbox[0].body)


class AttendanceAccessControlTests(TestCase):
    def setUp(self):
        self.student_user = CustomUser.objects.create_user(
            username="view_student",
            password="123456",
            role="STUDENT",
        )
        self.student = Student.objects.create(
            user=self.student_user,
            roll_number="S-1",
            class_name="8-A",
            phone="03000000000",
        )
        self.other_student_user = CustomUser.objects.create_user(
            username="other_student",
            password="123456",
            role="STUDENT",
        )
        self.other_student = Student.objects.create(
            user=self.other_student_user,
            roll_number="S-2",
            class_name="9-A",
            phone="03000000009",
        )

        self.teacher_user = CustomUser.objects.create_user(
            username="view_teacher",
            password="123456",
            role="TEACHER",
        )
        teacher = Teacher.objects.create(
            user=self.teacher_user,
            subject="Math",
            phone="03000000001",
        )
        classroom = Classroom.objects.create(name="8-A")
        teacher.classes.add(classroom)
        classroom.attendance_teacher = teacher
        classroom.save(update_fields=["attendance_teacher"])

    def test_student_cannot_open_mark_attendance(self):
        self.client.login(username="view_student", password="123456")
        response = self.client.get(reverse("mark_attendance"))

        self.assertEqual(response.status_code, 403)

    def test_student_can_open_attendance_report_and_only_view_own_records(self):
        Attendance.objects.create(student=self.student, date=localdate(), status="Present", marked_by="MANUAL")
        Attendance.objects.create(student=self.other_student, date=localdate(), status="Absent", marked_by="MANUAL")

        self.client.login(username="view_student", password="123456")
        response = self.client.get(reverse("attendance_report"))

        self.assertEqual(response.status_code, 200)
        records = list(response.context["records"])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].student_id, self.student.id)
        self.assertEqual(response.context["role"], "student")

    def test_teacher_can_open_mark_and_report(self):
        self.client.login(username="view_teacher", password="123456")

        mark_response = self.client.get(reverse("mark_attendance"), {"class": "8-A"})
        report_response = self.client.get(reverse("attendance_report"))

        self.assertEqual(mark_response.status_code, 200)
        self.assertEqual(report_response.status_code, 200)

    def test_admin_cannot_open_mark_attendance(self):
        admin_user = CustomUser.objects.create_user(
            username="view_admin",
            password="123456",
            role="ADMIN",
        )
        self.client.login(username=admin_user.username, password="123456")
        response = self.client.get(reverse("mark_attendance"))
        self.assertEqual(response.status_code, 403)

    def test_student_dashboard_attendance_route_supports_period_filters(self):
        Attendance.objects.create(student=self.student, date=localdate(), status="Present", marked_by="MANUAL")

        self.client.login(username="view_student", password="123456")
        response = self.client.get(reverse("student_attendance"), {"type": "weekly"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["role"], "student")
        self.assertEqual(response.context["report_type"], "weekly")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AttendanceFlowIntegrationTests(TestCase):
    def setUp(self):
        self.today = localdate()
        self.yesterday = self.today - timedelta(days=1)

        self.admin_user = CustomUser.objects.create_user(
            username="admin_user",
            password="123456",
            role="ADMIN",
        )
        self.teacher_user = CustomUser.objects.create_user(
            username="teacher_user",
            password="123456",
            role="TEACHER",
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            subject="Math",
            phone="03001112222",
        )
        self.class_8a = Classroom.objects.create(name="8-A")
        self.class_9a = Classroom.objects.create(name="9-A")
        self.teacher.classes.add(self.class_8a)
        self.class_8a.attendance_teacher = self.teacher
        self.class_8a.save(update_fields=["attendance_teacher"])

        self.s1 = Student.objects.create(
            user=CustomUser.objects.create_user(
                username="stu1",
                password="123456",
                role="STUDENT",
            ),
            roll_number="1",
            class_name="8-A",
            phone="03000000001",
            parent_email="p1@example.com",
        )
        self.s2 = Student.objects.create(
            user=CustomUser.objects.create_user(
                username="stu2",
                password="123456",
                role="STUDENT",
            ),
            roll_number="2",
            class_name="8-A",
            phone="03000000002",
            parent_email="p2@example.com",
        )
        self.other_class_student = Student.objects.create(
            user=CustomUser.objects.create_user(
                username="stu3",
                password="123456",
                role="STUDENT",
            ),
            roll_number="3",
            class_name="9-A",
            phone="03000000003",
            parent_email="p3@example.com",
        )

    def test_manual_attendance_create_then_update_without_duplicates(self):
        self.client.login(username="teacher_user", password="123456")

        post_data = {
            "class": "8-A",
            "date": self.today.isoformat(),
            "student_ids": [str(self.s1.id), str(self.s2.id)],
            f"status_{self.s1.id}": "Present",
            f"status_{self.s2.id}": "Absent",
        }
        response = self.client.post(
            reverse("mark_attendance"),
            post_data,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Attendance.objects.filter(date=self.today).count(), 2)
        self.assertTrue(
            Attendance.objects.filter(
                student=self.s1,
                date=self.today,
                status="Present",
                marked_by="MANUAL",
                marked_by_teacher=self.teacher,
                student_class="8-A",
            ).exists()
        )

        update_data = {
            "class": "8-A",
            "date": self.today.isoformat(),
            "student_ids": [str(self.s1.id), str(self.s2.id)],
            f"status_{self.s1.id}": "Absent",
            f"status_{self.s2.id}": "Absent",
        }
        response_update = self.client.post(
            reverse("mark_attendance"),
            update_data,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response_update.status_code, 200)
        self.assertEqual(Attendance.objects.filter(date=self.today).count(), 2)
        self.assertTrue(
            Attendance.objects.filter(
                student=self.s1,
                date=self.today,
                status="Absent",
                marked_by="MANUAL",
            ).exists()
        )

    def test_teacher_dashboard_counts_assigned_classes_only(self):
        Attendance.objects.create(
            student=self.s1,
            date=self.today,
            status="Present",
            marked_by="MANUAL",
        )
        Attendance.objects.create(
            student=self.s2,
            date=self.today,
            status="Absent",
            marked_by="MANUAL",
        )
        Attendance.objects.create(
            student=self.other_class_student,
            date=self.today,
            status="Present",
            marked_by="MANUAL",
        )

        self.client.login(username="teacher_user", password="123456")
        response = self.client.get(reverse("teacher_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["today_present"], 1)
        self.assertEqual(response.context["today_absent"], 1)
        self.assertEqual(response.context["total_students"], 2)

    def test_admin_dashboard_counts_today_attendance(self):
        Attendance.objects.create(
            student=self.s1,
            date=self.today,
            status="Present",
            marked_by="MANUAL",
        )
        Attendance.objects.create(
            student=self.s2,
            date=self.today,
            status="Absent",
            marked_by="MANUAL",
        )

        self.client.login(username="admin_user", password="123456")
        response = self.client.get(reverse("admin_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["today_present_count"], 1)
        self.assertEqual(response.context["today_absent_count"], 1)
        self.assertEqual(response.context["today_attendance"], 2)

    def test_attendance_report_filters_by_date_and_class(self):
        Attendance.objects.create(
            student=self.s1,
            date=self.today,
            status="Present",
            marked_by="MANUAL",
        )
        Attendance.objects.create(
            student=self.s2,
            date=self.yesterday,
            status="Absent",
            marked_by="MANUAL",
        )
        Attendance.objects.create(
            student=self.other_class_student,
            date=self.today,
            status="Present",
            marked_by="MANUAL",
        )

        self.client.login(username="teacher_user", password="123456")
        response = self.client.get(
            reverse("attendance_report"),
            {"type": "daily", "class": "8-A"},
        )

        self.assertEqual(response.status_code, 200)
        records = list(response.context["records"])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].student_id, self.s1.id)
        self.assertEqual(response.context["present"], 1)
        self.assertEqual(response.context["absent"], 0)

    def test_attendance_report_supports_weekly_and_monthly_filters(self):
        week_start = self.today - timedelta(days=self.today.weekday())
        within_week = week_start
        older_than_week = week_start - timedelta(days=1)
        previous_month = (self.today.replace(day=1) - timedelta(days=1)).replace(day=15)

        Attendance.objects.create(
            student=self.s1,
            date=within_week,
            status="Present",
            marked_by="MANUAL",
        )
        Attendance.objects.create(
            student=self.s2,
            date=older_than_week,
            status="Absent",
            marked_by="MANUAL",
        )
        Attendance.objects.create(
            student=self.other_class_student,
            date=previous_month,
            status="Present",
            marked_by="MANUAL",
        )

        self.client.login(username="admin_user", password="123456")

        weekly_response = self.client.get(reverse("attendance_report"), {"type": "weekly"})
        self.assertEqual(weekly_response.status_code, 200)
        weekly_dates = [record.date for record in weekly_response.context["records"]]
        self.assertIn(within_week, weekly_dates)
        self.assertNotIn(older_than_week, weekly_dates)

        monthly_response = self.client.get(reverse("attendance_report"), {"type": "monthly"})
        self.assertEqual(monthly_response.status_code, 200)
        monthly_dates = [record.date for record in monthly_response.context["records"]]
        month_start = self.today.replace(day=1)
        self.assertTrue(all(item >= month_start for item in monthly_dates))

    def test_month_selector_filters_specific_month(self):
        selected_month_date = (self.today.replace(day=1) - timedelta(days=1)).replace(day=10)
        other_month_date = self.today.replace(day=10)

        Attendance.objects.create(
            student=self.s1,
            date=selected_month_date,
            status="Present",
            marked_by="MANUAL",
        )
        Attendance.objects.create(
            student=self.s2,
            date=other_month_date,
            status="Absent",
            marked_by="MANUAL",
        )

        self.client.login(username="admin_user", password="123456")
        response = self.client.get(
            reverse("attendance_report"),
            {"type": "monthly", "month": selected_month_date.strftime("%Y-%m")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_month"], selected_month_date.strftime("%Y-%m"))
        self.assertEqual(response.context["selected_month_label"], selected_month_date.strftime("%B %Y"))
        records = list(response.context["records"])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].date.month, selected_month_date.month)
        self.assertEqual(records[0].date.year, selected_month_date.year)

    def test_attendance_report_builds_student_table_rows(self):
        Attendance.objects.create(
            student=self.s1,
            date=self.today,
            status="Present",
            marked_by="MANUAL",
        )
        Attendance.objects.create(
            student=self.s2,
            date=self.today,
            status="Absent",
            marked_by="MANUAL",
        )

        self.client.login(username="admin_user", password="123456")
        response = self.client.get(reverse("attendance_report"), {"type": "daily"})

        self.assertEqual(response.status_code, 200)
        rows = response.context["rows"]
        self.assertGreaterEqual(len(rows), 2)

        row_by_student = {row["student_id"]: row for row in rows}
        self.assertIn(self.s1.id, row_by_student)
        self.assertIn(self.s2.id, row_by_student)
        self.assertEqual(row_by_student[self.s1.id]["present_count"], 1)
        self.assertEqual(row_by_student[self.s1.id]["absent_count"], 0)
        self.assertEqual(row_by_student[self.s2.id]["present_count"], 0)
        self.assertEqual(row_by_student[self.s2.id]["absent_count"], 1)
        self.assertIn("weekly_percentage", row_by_student[self.s1.id])
        self.assertIn("monthly_percentage", row_by_student[self.s1.id])
        self.assertIn("status_label", row_by_student[self.s1.id])

    def test_attendance_report_supports_csv_and_excel_export(self):
        Attendance.objects.create(
            student=self.s1,
            date=self.today,
            status="Present",
            marked_by="MANUAL",
        )

        self.client.login(username="admin_user", password="123456")
        csv_response = self.client.get(reverse("attendance_report"), {"export": "csv"})
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("text/csv", csv_response["Content-Type"])
        self.assertIn("Student Name", csv_response.content.decode("utf-8"))

        excel_response = self.client.get(reverse("attendance_report"), {"export": "excel"})
        self.assertEqual(excel_response.status_code, 200)
        self.assertIn("application/vnd.ms-excel", excel_response["Content-Type"])
        self.assertIn("Student Name", excel_response.content.decode("utf-8"))

    def test_weekly_breakdown_contains_day_columns_and_status_cells(self):
        week_start = self.today - timedelta(days=self.today.weekday())
        monday = week_start
        tuesday = week_start + timedelta(days=1)

        Attendance.objects.create(
            student=self.s1,
            date=monday,
            status="Present",
            marked_by="MANUAL",
        )
        Attendance.objects.create(
            student=self.s1,
            date=tuesday,
            status="Absent",
            marked_by="MANUAL",
        )

        self.client.login(username="admin_user", password="123456")
        response = self.client.get(reverse("attendance_report"), {"type": "weekly"})

        self.assertEqual(response.status_code, 200)
        day_columns = response.context["day_columns"]
        self.assertEqual(len(day_columns), 7)
        self.assertEqual(day_columns[0]["label"], "Mon")
        self.assertEqual(day_columns[-1]["label"], "Sun")

        rows = response.context["rows"]
        row_by_student = {row["student_id"]: row for row in rows}
        self.assertIn(self.s1.id, row_by_student)
        self.assertEqual(len(row_by_student[self.s1.id]["daily_cells"]), 7)
        self.assertEqual(row_by_student[self.s1.id]["daily_cells"][0]["code"], "P")
        self.assertEqual(row_by_student[self.s1.id]["daily_cells"][1]["code"], "A")

    def test_monthly_breakdown_contains_day_numbers_and_status_cells(self):
        selected_month = self.today.strftime("%Y-%m")
        month_start = self.today.replace(day=1)
        second_day = month_start + timedelta(days=1)

        Attendance.objects.create(
            student=self.s1,
            date=month_start,
            status="Present",
            marked_by="MANUAL",
        )
        Attendance.objects.create(
            student=self.s1,
            date=second_day,
            status="Absent",
            marked_by="MANUAL",
        )

        self.client.login(username="admin_user", password="123456")
        response = self.client.get(
            reverse("attendance_report"),
            {"type": "monthly", "month": selected_month},
        )

        self.assertEqual(response.status_code, 200)
        day_columns = response.context["day_columns"]
        _, days_in_month = calendar.monthrange(self.today.year, self.today.month)
        self.assertEqual(len(day_columns), days_in_month)
        self.assertEqual(day_columns[0]["label"], "1")
        self.assertEqual(day_columns[1]["label"], "2")

        rows = response.context["rows"]
        row_by_student = {row["student_id"]: row for row in rows}
        self.assertIn(self.s1.id, row_by_student)
        self.assertEqual(row_by_student[self.s1.id]["daily_cells"][0]["code"], "P")
        self.assertEqual(row_by_student[self.s1.id]["daily_cells"][1]["code"], "A")

    def test_student_role_still_sees_only_own_breakdown_row(self):
        Attendance.objects.create(
            student=self.s1,
            date=self.today,
            status="Present",
            marked_by="MANUAL",
        )
        Attendance.objects.create(
            student=self.s2,
            date=self.today,
            status="Absent",
            marked_by="MANUAL",
        )

        self.client.login(username="stu1", password="123456")
        response = self.client.get(reverse("student_attendance"), {"type": "weekly"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["role"], "student")
        rows = response.context["rows"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["student_id"], self.s1.id)
        self.assertEqual(len(rows[0]["daily_cells"]), 7)
