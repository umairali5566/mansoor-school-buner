from django.urls import path
from . import views

urlpatterns = [

    path("upload/", views.upload_homework, name="upload_homework"),

    path("list/", views.homework_list, name="homework_list"),

]