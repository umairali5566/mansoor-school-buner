from django.db import models


class Homework(models.Model):

    title = models.CharField(max_length=200)

    description = models.TextField()

    class_name = models.CharField(max_length=50)

    file = models.FileField(upload_to="homework_files/", null=True, blank=True)

    date_assigned = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.title