from django.contrib import admin
from .models import Attendance

admin.site.register(Attendance)


from .models import ClassroomCamera

admin.site.register(ClassroomCamera)