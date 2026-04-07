from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from accounts.models import Classroom, CustomUser, Student, Teacher
from homework.models import Homework, Assignment, AssignmentSubmission, Quiz, Question, StudentQuizAttempt, Answer


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


class AssignmentSubmissionLogicTests(TestCase):
    def setUp(self):
        self.classroom = Classroom.objects.create(name="9-A")
        self.teacher_user = CustomUser.objects.create_user(
            username="assignment_teacher",
            password="123456",
            role="TEACHER",
        )
        teacher_profile = Teacher.objects.create(user=self.teacher_user, subject="Science", phone="03009999999")
        teacher_profile.classes.add(self.classroom)
        self.student_user = CustomUser.objects.create_user(
            username="assignment_student",
            password="123456",
            role="STUDENT",
        )
        Student.objects.create(
            user=self.student_user,
            roll_number="S-11",
            class_name="9-A",
            phone="03001112222",
        )
        self.assignment = Assignment.objects.create(
            title="Physics Assignment",
            description="Solve chapter questions",
            class_assigned=self.classroom,
            teacher=self.teacher_user,
            due_date=timezone.now() + timedelta(hours=1),
        )

    def test_submission_before_deadline_is_marked_submitted(self):
        submission = AssignmentSubmission.objects.create(
            assignment=self.assignment,
            student=self.student_user,
            file="assignment_submissions/test1.txt",
            submitted_at=timezone.now(),
        )
        self.assertEqual(submission.status, "Submitted")

    def test_submission_after_deadline_is_marked_late(self):
        submission = AssignmentSubmission.objects.create(
            assignment=self.assignment,
            student=self.student_user,
            file="assignment_submissions/test2.txt",
            submitted_at=self.assignment.due_date + timedelta(minutes=5),
        )
        self.assertEqual(submission.status, "Late")


class QuizAutoCheckingTests(TestCase):
    def setUp(self):
        self.classroom = Classroom.objects.create(name="8-B")
        self.teacher_user = CustomUser.objects.create_user(
            username="quiz_teacher",
            password="123456",
            role="TEACHER",
        )
        teacher_profile = Teacher.objects.create(user=self.teacher_user, subject="Math", phone="03007778888")
        teacher_profile.classes.add(self.classroom)

        self.student_user = CustomUser.objects.create_user(
            username="quiz_student",
            password="123456",
            role="STUDENT",
        )
        Student.objects.create(
            user=self.student_user,
            roll_number="Q-1",
            class_name="8-B",
            phone="03000000001",
        )

        self.quiz = Quiz.objects.create(
            title="Math Quiz",
            class_assigned=self.classroom,
            teacher=self.teacher_user,
            total_marks=2,
            time_limit=10,
        )
        self.q1 = Question.objects.create(
            quiz=self.quiz,
            question_text="2 + 2 = ?",
            option_a="3",
            option_b="4",
            option_c="5",
            option_d="6",
            correct_answer="B",
            order=1,
        )
        self.q2 = Question.objects.create(
            quiz=self.quiz,
            question_text="5 - 3 = ?",
            option_a="2",
            option_b="3",
            option_c="4",
            option_d="1",
            correct_answer="A",
            order=2,
        )

    def test_quiz_score_counts_correct_answers(self):
        attempt = StudentQuizAttempt.objects.create(student=self.student_user, quiz=self.quiz, score=0)
        Answer.objects.create(attempt=attempt, question=self.q1, selected_option="B")
        Answer.objects.create(attempt=attempt, question=self.q2, selected_option="C")

        score = Answer.objects.filter(
            attempt=attempt,
            selected_option=models.F("question__correct_answer"),
        ).count()
        attempt.score = score
        attempt.save(update_fields=["score"])

        self.assertEqual(attempt.score, 1)
        self.assertEqual(attempt.percentage, 50.0)


class AcademicPermissionTests(TestCase):
    def setUp(self):
        self.classroom = Classroom.objects.create(name="10-B")
        self.teacher_user = CustomUser.objects.create_user(
            username="perm_teacher",
            password="123456",
            role="TEACHER",
        )
        teacher_profile = Teacher.objects.create(user=self.teacher_user, subject="English", phone="03001231234")
        teacher_profile.classes.add(self.classroom)

        self.admin_user = CustomUser.objects.create_user(
            username="perm_admin",
            password="123456",
            role="ADMIN",
        )
        self.student_user = CustomUser.objects.create_user(
            username="perm_student",
            password="123456",
            role="STUDENT",
        )
        Student.objects.create(
            user=self.student_user,
            roll_number="P-1",
            class_name="10-B",
            phone="03009990000",
        )
        self.assignment = Assignment.objects.create(
            title="Permission Assignment",
            description="Check role restrictions",
            class_assigned=self.classroom,
            teacher=self.teacher_user,
            due_date=timezone.now() + timedelta(days=1),
        )

    def test_admin_cannot_create_assignment_or_quiz(self):
        self.client.login(username="perm_admin", password="123456")
        assignment_response = self.client.get(reverse("assignment_create"))
        quiz_response = self.client.get(reverse("quiz_create"))

        self.assertEqual(assignment_response.status_code, 403)
        self.assertEqual(quiz_response.status_code, 403)

        alias_assignment_response = self.client.get(reverse("create_assignment"))
        alias_quiz_response = self.client.get(reverse("create_quiz"))

        self.assertEqual(alias_assignment_response.status_code, 403)
        self.assertEqual(alias_quiz_response.status_code, 403)

    def test_teacher_can_create_assignment_and_quiz_pages(self):
        self.client.login(username="perm_teacher", password="123456")
        assignment_response = self.client.get(reverse("assignment_create"))
        quiz_response = self.client.get(reverse("quiz_create"))

        self.assertEqual(assignment_response.status_code, 200)
        self.assertEqual(quiz_response.status_code, 200)

        alias_assignment_response = self.client.get(reverse("create_assignment"))
        alias_quiz_response = self.client.get(reverse("create_quiz"))

        self.assertEqual(alias_assignment_response.status_code, 200)
        self.assertEqual(alias_quiz_response.status_code, 200)

    def test_admin_can_open_assignment_report_read_only(self):
        self.client.login(username="perm_admin", password="123456")
        response = self.client.get(reverse("assignment_detail", kwargs={"assignment_id": self.assignment.id}))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_manage"])
        self.assertTrue(response.context["is_admin_view"])

    def test_admin_cannot_open_homework_upload(self):
        self.client.login(username="perm_admin", password="123456")
        response = self.client.get(reverse("upload_homework"))
        self.assertEqual(response.status_code, 403)

    def test_teacher_assignment_list_uses_teacher_and_assigned_class_filter(self):
        other_teacher_user = CustomUser.objects.create_user(
            username="perm_teacher_other",
            password="123456",
            role="TEACHER",
        )
        other_teacher_profile = Teacher.objects.create(
            user=other_teacher_user,
            subject="History",
            phone="03004445555",
        )
        other_teacher_profile.classes.add(self.classroom)
        unassigned_classroom = Classroom.objects.create(name="11-B")

        visible_assignment = Assignment.objects.create(
            title="Visible Assignment",
            description="Should appear",
            class_assigned=self.classroom,
            teacher=self.teacher_user,
            due_date=timezone.now() + timedelta(days=1),
        )
        Assignment.objects.create(
            title="Hidden Unassigned Class",
            description="Teacher created but class not assigned",
            class_assigned=unassigned_classroom,
            teacher=self.teacher_user,
            due_date=timezone.now() + timedelta(days=1),
        )
        other_teacher_assignment = Assignment.objects.create(
            title="Hidden Other Teacher",
            description="Different teacher, same class",
            class_assigned=self.classroom,
            teacher=other_teacher_user,
            due_date=timezone.now() + timedelta(days=1),
        )

        self.client.login(username="perm_teacher", password="123456")
        response = self.client.get(reverse("assignment_list"))
        self.assertEqual(response.status_code, 200)

        assignment_titles = {
            card["assignment"].title
            for card in response.context["assignment_cards"]
        }
        self.assertIn(visible_assignment.title, assignment_titles)
        self.assertNotIn("Hidden Unassigned Class", assignment_titles)
        self.assertNotIn(other_teacher_assignment.title, assignment_titles)

    def test_teacher_quiz_list_uses_teacher_and_assigned_class_filter(self):
        other_teacher_user = CustomUser.objects.create_user(
            username="perm_quiz_other",
            password="123456",
            role="TEACHER",
        )
        other_teacher_profile = Teacher.objects.create(
            user=other_teacher_user,
            subject="Chemistry",
            phone="03006667777",
        )
        other_teacher_profile.classes.add(self.classroom)
        unassigned_classroom = Classroom.objects.create(name="12-B")

        visible_quiz = Quiz.objects.create(
            title="Visible Quiz",
            class_assigned=self.classroom,
            teacher=self.teacher_user,
            total_marks=10,
            time_limit=15,
        )
        Quiz.objects.create(
            title="Hidden Quiz Unassigned Class",
            class_assigned=unassigned_classroom,
            teacher=self.teacher_user,
            total_marks=10,
            time_limit=15,
        )
        other_teacher_quiz = Quiz.objects.create(
            title="Hidden Quiz Other Teacher",
            class_assigned=self.classroom,
            teacher=other_teacher_user,
            total_marks=10,
            time_limit=15,
        )

        self.client.login(username="perm_teacher", password="123456")
        response = self.client.get(reverse("quiz_list"))
        self.assertEqual(response.status_code, 200)

        quiz_titles = {
            row["quiz"].title
            for row in response.context["quizzes"]
        }
        self.assertIn(visible_quiz.title, quiz_titles)
        self.assertNotIn("Hidden Quiz Unassigned Class", quiz_titles)
        self.assertNotIn(other_teacher_quiz.title, quiz_titles)

    def test_student_assignment_list_marks_expired_without_submission_as_late(self):
        expired_assignment = Assignment.objects.create(
            title="Expired Assignment",
            description="Past due",
            class_assigned=self.classroom,
            teacher=self.teacher_user,
            due_date=timezone.now() - timedelta(days=1),
        )

        self.client.login(username="perm_student", password="123456")
        response = self.client.get(reverse("assignment_list"))
        self.assertEqual(response.status_code, 200)

        cards = {
            card["assignment"].id: card
            for card in response.context["assignment_cards"]
        }
        self.assertIn(expired_assignment.id, cards)
        self.assertEqual(cards[expired_assignment.id]["my_status"], "Late")
