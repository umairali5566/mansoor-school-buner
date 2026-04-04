from django.core import mail
from django.test import TestCase, override_settings

from accounts.models import CustomUser, Student
from results.models import Result


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ResultNotificationTests(TestCase):
    def setUp(self):
        user = CustomUser.objects.create_user(
            username="student_result",
            password="123456",
            role="STUDENT",
            first_name="Result",
            last_name="Student",
        )
        self.student = Student.objects.create(
            user=user,
            roll_number="R-1",
            class_name="9-A",
            phone="03002222222",
            parent_email="parent-result@example.com",
        )

    def test_result_create_sends_parent_notification(self):
        result = Result.objects.create(
            student=self.student,
            subject="Physics",
            marks=88,
            total_marks=100,
            exam_type="Midterm",
        )

        result.refresh_from_db()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("New Result Uploaded", mail.outbox[0].subject)
        self.assertIn("Physics", mail.outbox[0].body)
        self.assertIsNotNone(result.notification_sent_at)

    def test_result_update_does_not_resend_duplicate_email(self):
        result = Result.objects.create(
            student=self.student,
            subject="Biology",
            marks=78,
            total_marks=100,
            exam_type="Final",
        )
        self.assertEqual(len(mail.outbox), 1)

        result.marks = 79
        result.save()

        self.assertEqual(len(mail.outbox), 1)

    def test_no_parent_email_skips_sending(self):
        self.student.parent_email = ""
        self.student.save(update_fields=["parent_email"])

        result = Result.objects.create(
            student=self.student,
            subject="Chemistry",
            marks=90,
            total_marks=100,
            exam_type="Final",
        )

        result.refresh_from_db()
        self.assertEqual(len(mail.outbox), 0)
        self.assertIsNone(result.notification_sent_at)
