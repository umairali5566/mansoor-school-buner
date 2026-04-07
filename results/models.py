from django.db import models
from accounts.models import Student
from accounts.models import Teacher

class Result(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="results_created",
    )
    subject = models.CharField(max_length=100)
    marks = models.IntegerField()
    total_marks = models.IntegerField(default=100)
    exam_type = models.CharField(max_length=50)  # Midterm / Final
    date = models.DateField(auto_now_add=True)
    notification_sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.student.user.username} - {self.subject}"
