from django import forms

from accounts.forms import get_student_full_name, student_roll_number_exists
from accounts.models import Student


class FaceUploadForm(forms.Form):
    image = forms.ImageField()


class ConvertUnknownForm(forms.Form):
    ADD_NEW_SENTINEL = "__new__"

    student_choice = forms.ChoiceField(
        choices=(),
        widget=forms.Select(
            attrs={
                "class": "form-select",
                "id": "id_student_choice",
            }
        ),
    )

    full_name = forms.CharField(
        required=False,
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Student full name",
            }
        ),
    )
    roll_number = forms.CharField(
        required=False,
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Roll number",
            }
        ),
    )
    class_name = forms.CharField(
        required=False,
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Class (e.g. 9th-A)",
            }
        ),
    )
    parent_phone = forms.CharField(
        required=False,
        max_length=15,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Parent phone",
            }
        ),
    )
    parent_email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "Parent email (optional)",
            }
        ),
    )
    student_image = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(
            attrs={
                "class": "form-control",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.students = Student.objects.select_related("user").order_by(
            "class_name",
            "roll_number",
            "user__username",
        )
        choices = [("", "Select Existing Student")]
        for student in self.students:
            display_name = get_student_full_name(student)
            choices.append(
                (
                    str(student.id),
                    f"{display_name} | Roll {student.roll_number} | {student.class_name}",
                )
            )
        choices.append((self.ADD_NEW_SENTINEL, "+ Add New Student"))
        self.fields["student_choice"].choices = choices

    def clean(self):
        cleaned_data = super().clean()
        student_choice = (cleaned_data.get("student_choice") or "").strip()
        cleaned_data["student_choice"] = student_choice

        cleaned_data["full_name"] = (cleaned_data.get("full_name") or "").strip()
        cleaned_data["roll_number"] = (cleaned_data.get("roll_number") or "").strip()
        cleaned_data["class_name"] = (cleaned_data.get("class_name") or "").strip()
        cleaned_data["parent_phone"] = (cleaned_data.get("parent_phone") or "").strip()

        parent_email = (cleaned_data.get("parent_email") or "").strip()
        cleaned_data["parent_email"] = parent_email

        if not student_choice:
            self.add_error("student_choice", "Select an existing student or choose + Add New Student.")
            return cleaned_data

        if student_choice == self.ADD_NEW_SENTINEL:
            cleaned_data["create_new_student"] = True

            required_new_student_fields = (
                "full_name",
                "roll_number",
                "class_name",
                "parent_phone",
            )
            for field_name in required_new_student_fields:
                if not cleaned_data.get(field_name):
                    self.add_error(field_name, "This field is required when creating a new student.")

            roll_number = cleaned_data.get("roll_number")
            class_name = cleaned_data.get("class_name")
            if roll_number and class_name and student_roll_number_exists(roll_number, class_name):
                self.add_error("roll_number", "A student with this roll number already exists in this class.")

            return cleaned_data

        cleaned_data["create_new_student"] = False
        student = self.students.filter(id=student_choice).first()
        if student is None:
            self.add_error("student_choice", "Selected student does not exist.")
            return cleaned_data

        cleaned_data["student"] = student
        return cleaned_data
