from django.urls import path
from . import views

urlpatterns = [
    path('add/', views.add_result, name='add_result'),
    path('list/', views.result_list, name='result_list'),
]