from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.timezone import localdate

# =========================
# Custom User Model
# =========================
class CustomUser(AbstractUser):

    ROLE_CHOICES = (
        ('ADMIN', 'Admin'),
        ('TEACHER', 'Teacher'),
        ('STUDENT', 'Student'),
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    def __str__(self):
        return self.username


# =========================
# Student Model
# =========================
class Student(models.Model):

    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)

    full_name = models.CharField(max_length=150, blank=True)

    roll_number = models.CharField(max_length=20)

    class_name = models.CharField(max_length=20, db_index=True)

    date_of_birth = models.DateField(blank=True, null=True)

    admission_date = models.DateField(default=localdate, db_index=True)

    previous_school = models.CharField(max_length=255, blank=True)

    admission_class = models.ForeignKey(
        "Classroom",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="admitted_students",
    )

    phone = models.CharField(max_length=15)

    parent_email = models.EmailField(blank=True, null=True)

    notes = models.TextField(blank=True)

    image = models.ImageField(upload_to='student_photos/', blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["roll_number", "class_name"],
                name="unique_student_roll_number_per_class",
            )
        ]
        indexes = [
            models.Index(fields=["admission_date", "class_name"]),
        ]

    @property
    def display_name(self):
        return self.full_name or self.user.get_full_name().strip() or self.user.username

    @property
    def current_class(self):
        return self.class_name

    @current_class.setter
    def current_class(self, value):
        if value is None:
            self.class_name = ""
        elif hasattr(value, "name"):
            self.class_name = value.name
        else:
            self.class_name = str(value).strip()

    @property
    def admission_class_name(self):
        return self.admission_class.name if self.admission_class else "-"

    def save(self, *args, **kwargs):
        if self.user_id:
            resolved_name = (self.full_name or self.user.get_full_name().strip() or self.user.username).strip()
            self.full_name = resolved_name or self.user.username

        self.roll_number = (self.roll_number or "").strip()
        self.class_name = (self.class_name or "").strip()
        self.previous_school = (self.previous_school or "").strip()

        if not self.class_name and self.admission_class_id:
            self.class_name = self.admission_class.name

        if not self.admission_class_id and self.class_name:
            matching_classroom = Classroom.objects.filter(name__iexact=self.class_name).first()
            if matching_classroom is not None:
                self.admission_class = matching_classroom

        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name

# =========================
# Classroom Model
# =========================
class Classroom(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


# =========================
# Teacher Model
# =========================
class Teacher(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    subject = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    # a teacher may teach multiple classes
    classes = models.ManyToManyField(Classroom, blank=True, related_name='teachers')

    def __str__(self):
        return self.user.username
