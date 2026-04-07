import pickle
from django.db import models
from django.utils import timezone
from django.utils.timezone import localdate
from accounts.models import Student


class Attendance(models.Model):

    STATUS = (
        ('Present', 'Present'),
        ('Absent', 'Absent'),
    )
    MARKED_BY = (
        ("FACE", "Face Recognition"),
        ("MANUAL", "Teacher Manual"),
        ("AUTO_ABSENT", "Auto Absent"),
        ("SYSTEM", "System"),
    )

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    student_class = models.CharField(max_length=20, blank=True, default="", db_index=True)
    date = models.DateField(default=localdate)
    status = models.CharField(max_length=10, choices=STATUS)
    created_at = models.DateTimeField(default=timezone.now)
    marked_at = models.DateTimeField(default=timezone.now)
    marked_by = models.CharField(max_length=20, choices=MARKED_BY, default="SYSTEM")
    marked_by_teacher = models.ForeignKey(
        "accounts.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_marks",
    )
    notification_sent_at = models.DateTimeField(null=True, blank=True)
    notification_status = models.CharField(max_length=10, blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "date"],
                name="unique_student_attendance_per_day",
            )
        ]
        indexes = [
            models.Index(fields=["date", "status"]),
            models.Index(fields=["date", "student_class"]),
        ]

    def save(self, *args, **kwargs):
        if self.student_id and not self.student_class:
            self.student_class = self.student.class_name or ""
        super().save(*args, **kwargs)

    def __str__(self):
        student_name = self.student.user.get_full_name() or self.student.user.username
        return f"{student_name} - {self.status}"


class StudentFaceData(models.Model):

    student = models.OneToOneField(Student, on_delete=models.CASCADE)

    image = models.ImageField(upload_to='student_faces/', null=True, blank=True)

    encoding = models.BinaryField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def set_encoding(self, encoding_array):
        self.encoding = pickle.dumps(encoding_array)

    def get_encoding(self):
        if self.encoding:
            return pickle.loads(self.encoding)
        return None

    def __str__(self):
        return self.student.user.username


class ClassroomCamera(models.Model):

    class_name = models.CharField(max_length=50)

    camera_index = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.class_name} - Camera {self.camera_index}"


class UnknownFace(models.Model):

    image = models.ImageField(upload_to="unknown_faces/")

    captured_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Unknown - {self.captured_at}"
