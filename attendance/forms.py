from django import forms

class FaceUploadForm(forms.Form):
    image = forms.ImageField()


from accounts.models import Student

class ConvertUnknownForm(forms.Form):
    student = forms.ModelChoiceField(queryset=Student.objects.all())