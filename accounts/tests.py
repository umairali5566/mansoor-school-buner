from datetime import date

from django.test import TestCase
from django.urls import reverse

from accounts.forms import StudentAdmissionForm
from accounts.models import Classroom, CustomUser, Student


class StudentAdmissionFormTests(TestCase):
    def setUp(self):
        self.class_8a = Classroom.objects.create(name="8-A")
        self.class_9a = Classroom.objects.create(name="9-A")
        self.existing_student = Student.objects.create(
            user=CustomUser.objects.create_user(
                username="existingstudent",
                password="123456",
                role="STUDENT",
                first_name="Existing",
                last_name="Student",
            ),
            roll_number="12",
            class_name="8-A",
            admission_class=self.class_8a,
            admission_date=date(2026, 1, 10),
            date_of_birth=date(2012, 5, 4),
            phone="03001112222",
            parent_email="parent@example.com",
        )

    def test_duplicate_roll_number_is_rejected_per_class(self):
        form = StudentAdmissionForm(
            data={
                "full_name": "Ali Khan",
                "roll_number": "12",
                "date_of_birth": "2013-02-01",
                "admission_date": "2026-01-15",
                "admission_class": self.class_8a.id,
                "current_class": self.class_8a.id,
                "previous_school": "City School",
                "parent_email": "ali.parent@example.com",
                "phone": "03009998888",
                "notes": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("roll_number", form.errors)

    def test_form_save_creates_student_with_admission_fields(self):
        form = StudentAdmissionForm(
            data={
                "full_name": "Sara Noor",
                "roll_number": "25",
                "date_of_birth": "2013-04-18",
                "admission_date": "2026-02-01",
                "admission_class": self.class_8a.id,
                "current_class": self.class_9a.id,
                "previous_school": "Green Valley School",
                "parent_email": "sara.parent@example.com",
                "phone": "03005556666",
                "notes": "Promoted after placement review.",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        student = form.save()

        self.assertEqual(student.full_name, "Sara Noor")
        self.assertEqual(student.roll_number, "25")
        self.assertEqual(student.date_of_birth, date(2013, 4, 18))
        self.assertEqual(student.admission_date, date(2026, 2, 1))
        self.assertEqual(student.admission_class, self.class_8a)
        self.assertEqual(student.class_name, "9-A")
        self.assertEqual(student.previous_school, "Green Valley School")
        self.assertEqual(student.parent_email, "sara.parent@example.com")
        self.assertEqual(student.phone, "03005556666")
        self.assertEqual(student.notes, "Promoted after placement review.")


class StudentAdmissionViewTests(TestCase):
    def setUp(self):
        self.admin_user = CustomUser.objects.create_user(
            username="admin",
            password="123456",
            role="ADMIN",
        )
        self.class_8a = Classroom.objects.create(name="8-A")
        self.class_9a = Classroom.objects.create(name="9-A")

        self.student_one = Student.objects.create(
            user=CustomUser.objects.create_user(
                username="alikhan1",
                password="123456",
                role="STUDENT",
                first_name="Ali",
                last_name="Khan",
            ),
            full_name="Ali Khan",
            roll_number="1",
            class_name="8-A",
            date_of_birth=date(2012, 1, 10),
            admission_date=date(2026, 1, 1),
            admission_class=self.class_8a,
            previous_school="River School",
            phone="03001110000",
            parent_email="ali.parent@example.com",
        )
        self.student_two = Student.objects.create(
            user=CustomUser.objects.create_user(
                username="ahmad2",
                password="123456",
                role="STUDENT",
                first_name="Ahmad",
                last_name="Raza",
            ),
            full_name="Ahmad Raza",
            roll_number="2",
            class_name="9-A",
            date_of_birth=date(2011, 8, 20),
            admission_date=date(2026, 2, 5),
            admission_class=self.class_9a,
            previous_school="Model School",
            phone="03002220000",
            parent_email="ahmad.parent@example.com",
        )

    def test_student_admissions_view_filters_records(self):
        self.client.login(username="admin", password="123456")
        response = self.client.get(
            reverse("student_admissions"),
            {
                "q": "Ali",
                "class_id": str(self.class_8a.id),
                "admission_date": "2026-01-01",
            },
        )

        self.assertEqual(response.status_code, 200)
        records = list(response.context["students"])
        self.assertEqual(records, [self.student_one])

    def test_add_student_admission_view_creates_student(self):
        self.client.login(username="admin", password="123456")
        response = self.client.post(
            reverse("add_student_admission"),
            {
                "full_name": "Fatima Zahra",
                "roll_number": "14",
                "date_of_birth": "2013-03-12",
                "admission_date": "2026-03-01",
                "admission_class": self.class_8a.id,
                "current_class": self.class_9a.id,
                "previous_school": "Beacon School",
                "parent_email": "fatima.parent@example.com",
                "phone": "03003334444",
                "notes": "Transferred from another campus.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/student_created.html")

        student = Student.objects.get(roll_number="14", class_name="9-A")
        self.assertEqual(student.full_name, "Fatima Zahra")
        self.assertEqual(student.admission_class, self.class_8a)
        self.assertEqual(student.previous_school, "Beacon School")
        self.assertContains(response, student.user.username)
