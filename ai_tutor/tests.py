from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser, Student, Teacher

from .models import ChatHistory


class AiTutorAccessTests(TestCase):
    def setUp(self):
        self.student_user = CustomUser.objects.create_user(
            username="ai_student",
            password="12345678",
            role="STUDENT",
        )
        Student.objects.create(
            user=self.student_user,
            full_name="AI Student",
            roll_number="A-1",
            class_name="10-A",
            phone="03000000000",
        )

        self.teacher_user = CustomUser.objects.create_user(
            username="ai_teacher",
            password="12345678",
            role="TEACHER",
        )
        Teacher.objects.create(
            user=self.teacher_user,
            subject="Math",
            phone="03001111111",
        )

        self.admin_user = CustomUser.objects.create_user(
            username="ai_admin",
            password="12345678",
            role="ADMIN",
        )

    def test_student_can_open_chat_page(self):
        self.client.login(username="ai_student", password="12345678")
        response = self.client.get(reverse("ai_tutor_chat"))
        self.assertEqual(response.status_code, 200)

    def test_teacher_cannot_open_chat_page(self):
        self.client.login(username="ai_teacher", password="12345678")
        response = self.client.get(reverse("ai_tutor_chat"))
        self.assertEqual(response.status_code, 403)

    def test_admin_cannot_open_chat_page(self):
        self.client.login(username="ai_admin", password="12345678")
        response = self.client.get(reverse("ai_tutor_chat"))
        self.assertEqual(response.status_code, 403)

    @patch("ai_tutor.views.generate_ai_tutor_reply", return_value="2 + 2 = 4.")
    def test_student_can_send_message_and_history_is_saved(self, mocked_reply):
        self.client.login(username="ai_student", password="12345678")
        response = self.client.post(
            reverse("ai_tutor_send"),
            data='{"question":"What is 2 + 2?"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ChatHistory.objects.count(), 1)
        history = ChatHistory.objects.first()
        self.assertEqual(history.question, "What is 2 + 2?")
        self.assertEqual(history.answer, "2 + 2 = 4.")
        mocked_reply.assert_called_once()

