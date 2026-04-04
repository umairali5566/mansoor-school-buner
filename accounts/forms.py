from django import forms
from django.utils.timezone import localdate

from .models import Classroom, CustomUser, Student, Teacher


DEFAULT_PASSWORD = "123456"


def split_full_name(full_name):
    parts = full_name.strip().split()
    if not parts:
        return "", ""
    first_name = parts[0]
    last_name = " ".join(parts[1:])
    return first_name, last_name


def get_student_full_name(student):
    if student is None:
        return ""
    return (student.full_name or student.user.get_full_name().strip() or student.user.username).strip()


def build_student_username(full_name, roll_number):
    name_token = "".join(ch for ch in full_name.lower() if ch.isalnum())
    roll_token = "".join(ch for ch in roll_number.lower() if ch.isalnum())
    base = f"{name_token}{roll_token}" or "student"

    username = base
    counter = 1
    while CustomUser.objects.filter(username=username).exists():
        username = f"{base}{counter}"
        counter += 1
    return username


def student_roll_number_exists(roll_number, class_name, *, exclude_student=None):
    queryset = Student.objects.filter(
        roll_number__iexact=(roll_number or "").strip(),
        class_name__iexact=(class_name or "").strip(),
    )
    if exclude_student is not None:
        queryset = queryset.exclude(pk=exclude_student.pk)
    return queryset.exists()


class StudentAdmissionForm(forms.Form):
    full_name = forms.CharField(max_length=150, required=True)
    roll_number = forms.CharField(max_length=20, required=True)
    date_of_birth = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    admission_date = forms.DateField(
        required=True,
        initial=localdate,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    admission_class = forms.ModelChoiceField(
        queryset=Classroom.objects.none(),
        required=True,
        empty_label="Select admission class",
    )
    current_class = forms.ModelChoiceField(
        queryset=Classroom.objects.none(),
        required=True,
        empty_label="Select current class",
    )
    previous_school = forms.CharField(max_length=255, required=False)
    parent_email = forms.EmailField(required=True)
    phone = forms.CharField(max_length=15, required=True)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))

    def __init__(self, *args, student=None, **kwargs):
        self.student = student
        initial = kwargs.pop("initial", {})

        if student is not None:
            initial = {
                "full_name": get_student_full_name(student),
                "roll_number": student.roll_number,
                "date_of_birth": student.date_of_birth,
                "admission_date": student.admission_date,
                "admission_class": student.admission_class_id,
                "current_class": Classroom.objects.filter(name__iexact=student.class_name).values_list("id", flat=True).first(),
                "previous_school": student.previous_school,
                "parent_email": student.parent_email or "",
                "phone": student.phone,
                "notes": student.notes,
                **initial,
            }

        kwargs["initial"] = initial
        super().__init__(*args, **kwargs)

        classroom_queryset = Classroom.objects.order_by("name")
        self.fields["admission_class"].queryset = classroom_queryset
        self.fields["current_class"].queryset = classroom_queryset

        for name, field in self.fields.items():
            existing_class = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (f"{existing_class} form-control").strip()
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = (f"{existing_class} form-select").strip()

        self.fields["full_name"].widget.attrs.update({"placeholder": "Enter student full name"})
        self.fields["roll_number"].widget.attrs.update({"placeholder": "Enter roll number"})
        self.fields["previous_school"].widget.attrs.update({"placeholder": "Previous school name"})
        self.fields["phone"].widget.attrs.update({"placeholder": "Parent phone number"})
        self.fields["parent_email"].widget.attrs.update({"placeholder": "Parent email address"})
        self.fields["notes"].widget.attrs.update({"placeholder": "Internal admission notes"})

    def clean_full_name(self):
        value = (self.cleaned_data.get("full_name") or "").strip()
        if not value:
            raise forms.ValidationError("Full name is required.")
        return value

    def clean_roll_number(self):
        value = (self.cleaned_data.get("roll_number") or "").strip()
        if not value:
            raise forms.ValidationError("Roll number is required.")
        return value

    def clean_phone(self):
        value = (self.cleaned_data.get("phone") or "").strip()
        if not value:
            raise forms.ValidationError("Phone number is required.")
        return value

    def clean_parent_email(self):
        value = (self.cleaned_data.get("parent_email") or "").strip()
        if not value:
            raise forms.ValidationError("Parent email is required.")
        return value

    def clean_previous_school(self):
        return (self.cleaned_data.get("previous_school") or "").strip()

    def clean_notes(self):
        return (self.cleaned_data.get("notes") or "").strip()

    def clean(self):
        cleaned_data = super().clean()
        roll_number = cleaned_data.get("roll_number")
        current_class = cleaned_data.get("current_class")
        admission_date = cleaned_data.get("admission_date")
        date_of_birth = cleaned_data.get("date_of_birth")

        if current_class and roll_number:
            if student_roll_number_exists(
                roll_number,
                current_class.name,
                exclude_student=self.student,
            ):
                self.add_error(
                    "roll_number",
                    "This roll number already exists in the selected current class.",
                )

        if date_of_birth and admission_date and admission_date <= date_of_birth:
            self.add_error(
                "admission_date",
                "Admission date must be later than the date of birth.",
            )

        return cleaned_data

    def save(self):
        full_name = self.cleaned_data["full_name"]
        roll_number = self.cleaned_data["roll_number"]
        current_class = self.cleaned_data["current_class"]
        first_name, last_name = split_full_name(full_name)

        if self.student is None:
            username = build_student_username(full_name, roll_number)
            user = CustomUser.objects.create_user(
                username=username,
                password=DEFAULT_PASSWORD,
                role="STUDENT",
                first_name=first_name,
                last_name=last_name,
            )
            student = Student(user=user)
            self.generated_username = username
            self.generated_password = DEFAULT_PASSWORD
        else:
            student = self.student
            user = student.user
            user.first_name = first_name
            user.last_name = last_name

        user.first_name = first_name
        user.last_name = last_name
        user.save(update_fields=["first_name", "last_name"])

        student.full_name = full_name
        student.roll_number = roll_number
        student.date_of_birth = self.cleaned_data["date_of_birth"]
        student.admission_date = self.cleaned_data["admission_date"]
        student.admission_class = self.cleaned_data["admission_class"]
        student.current_class = current_class
        student.previous_school = self.cleaned_data["previous_school"]
        student.phone = self.cleaned_data["phone"]
        student.parent_email = self.cleaned_data["parent_email"]
        student.notes = self.cleaned_data["notes"]
        student.save()

        return student


class StudentCreateForm(StudentAdmissionForm):
    pass


class TeacherCreateForm(forms.Form):
    full_name = forms.CharField(max_length=150)
    subject = forms.CharField(max_length=100)
    phone = forms.CharField(max_length=15)

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        username = "".join(phone.split())
        if not username:
            raise forms.ValidationError("Phone number is required.")
        if CustomUser.objects.filter(username=username).exists():
            raise forms.ValidationError("A teacher account with this phone already exists.")
        return phone

    def save(self):
        full_name = self.cleaned_data["full_name"]
        phone = self.cleaned_data["phone"]
        username = "".join(phone.split())
        first_name, last_name = split_full_name(full_name)

        user = CustomUser.objects.create_user(
            username=username,
            password=DEFAULT_PASSWORD,
            role="TEACHER",
            first_name=first_name,
            last_name=last_name,
        )

        Teacher.objects.create(
            user=user,
            subject=self.cleaned_data["subject"],
            phone=phone,
        )

        self.generated_username = username
        self.generated_password = DEFAULT_PASSWORD
        return user


class AdminStudentProfileEditForm(StudentAdmissionForm):
    pass
