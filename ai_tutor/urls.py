from django.urls import path

from . import views


urlpatterns = [
    path("", views.ai_tutor_chat, name="ai_tutor_chat"),
    path("send/", views.ai_tutor_send, name="ai_tutor_send"),
]

