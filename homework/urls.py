from django.urls import path
from . import views

urlpatterns = [

    path("upload/", views.upload_homework, name="upload_homework"),

    path("list/", views.homework_list, name="homework_list"),

    path("<int:homework_id>/download/", views.download_homework, name="download_homework"),

]
