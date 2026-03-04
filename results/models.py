from django.db import models
from accounts.models import Student

class Result(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    subject = models.CharField(max_length=100)
    marks = models.IntegerField()
    total_marks = models.IntegerField(default=100)
    exam_type = models.CharField(max_length=50)  # Midterm / Final
    date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.user.username} - {self.subject}"