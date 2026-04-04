from django.core import mail
from django.test import TestCase, override_settings

from accounts.models import Classroom, CustomUser, Student, Teacher
from homework.models import Homework


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class HomeworkNotificationTests(TestCase):
    def setUp(self):
        teacher_user = CustomUser.objects.create_user(
            username="teacher1",
            password="123456",
            role="TEACHER",
            first_name="Teacher",
            last_name="One",
        )
        self.teacher = Teacher.objects.create(user=teacher_user, subject="Math", phone="03000000000")
        self.classroom = Classroom.objects.create(name="10-A")
        self.teacher.classes.add(self.classroom)

        for index in range(2):
            user = CustomUser.objects.create_user(
                username=f"student{index}",
                password="123456",
                role="STUDENT",
                first_name=f"Student{index}",
                last_name="Test",
            )
            Student.objects.create(
                user=user,
                roll_number=f"R-{index}",
                class_name="10-A",
                phone="03001111111",
                parent_email=f"parent{index}@example.com",
            )

    def test_homework_create_sends_parent_notifications(self):
        homework = Homework.objects.create(
            title="Chapter 1 Questions",
            description="Solve exercise 1 to 5.",
            class_name="10-A",
            subject="Math",
            teacher=self.teacher,
        )

        homework.refresh_from_db()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("New Homework Assigned", mail.outbox[0].subject)
        self.assertEqual(len(mail.outbox[0].to), 2)
        self.assertIsNotNone(homework.notification_sent_at)

    def test_homework_update_does_not_resend_duplicate_email(self):
        homework = Homework.objects.create(
            title="Worksheet",
            description="Complete worksheet.",
            class_name="10-A",
            subject="Science",
            teacher=self.teacher,
        )
        self.assertEqual(len(mail.outbox), 1)

        homework.title = "Worksheet Updated"
        homework.save()

        self.assertEqual(len(mail.outbox), 1)
