import pickle
from django.db import models
from accounts.models import Student



class Attendance(models.Model):

    STATUS = (
        ('Present', 'Present'),
        ('Absent', 'Absent'),
    )

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS)

    def __str__(self):
        return f"{self.student.name} - {self.status}"

class StudentFaceData(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE)
    encoding = models.BinaryField()

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