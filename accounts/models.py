from django.db import models
from django.contrib.auth.models import AbstractUser

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
    roll_number = models.CharField(max_length=20)
    class_name = models.CharField(max_length=20, null=True, blank=True)
    phone = models.CharField(max_length=15)
    face_image = models.ImageField(upload_to="faces/", null=True, blank=True)

    
    def __str__(self):
        return self.user.username


# =========================
# Teacher Model
# =========================
class Teacher(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    subject = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)

    def __str__(self):
        return self.user.username