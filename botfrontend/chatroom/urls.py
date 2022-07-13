from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('room_photos', views.room_photos, name='room_photos'),
]
