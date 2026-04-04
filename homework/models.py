from django.db import models
from accounts.models import Teacher


class Homework(models.Model):

    title = models.CharField(max_length=200)

    description = models.TextField()

    class_name = models.CharField(max_length=50)

    subject = models.CharField(max_length=100, default="General")

    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="homeworks",
    )

    file = models.FileField(upload_to="homework_files/", null=True, blank=True)

    date_assigned = models.DateField(auto_now_add=True)

    due_date = models.DateField(null=True, blank=True)
    notification_sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title
