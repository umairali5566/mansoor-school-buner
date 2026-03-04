from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.hashers import make_password
from django.utils.crypto import get_random_string
from .models import CustomUser, Student, Teacher
from .models import CustomUser, Student
import random
import string


class StudentCreateForm(forms.Form):

    username = forms.CharField(max_length=150)
    roll_number = forms.CharField(max_length=20)
    class_name = forms.CharField(max_length=20)
    phone = forms.CharField(max_length=15)

    def save(self):

        password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))

        user = CustomUser.objects.create(
            username=self.cleaned_data["username"],
            password=make_password(password),
            role="STUDENT"
        )

        Student.objects.create(
            user=user,
            roll_number=self.cleaned_data["roll_number"],
            class_name=self.cleaned_data["class_name"],
            phone=self.cleaned_data["phone"]
        )

        self.generated_password = password

        return user

class TeacherCreateForm(forms.ModelForm):
    subject = forms.CharField(max_length=100)
    phone = forms.CharField(max_length=15)

    class Meta:
        model = CustomUser
        fields = ['username']

    def save(self, commit=True):
        password = get_random_string(8)

        user = CustomUser(
            username=self.cleaned_data['username'],
            role="TEACHER",
            password=make_password(password)
        )

        if commit:
            user.save()
            Teacher.objects.create(
                user=user,
                subject=self.cleaned_data['subject'],
                phone=self.cleaned_data['phone']
            )

        self.generated_password = password
        return user