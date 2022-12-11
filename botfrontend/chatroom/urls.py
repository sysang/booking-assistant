from django.urls import path

from . import views

app_name = 'chatroom'
urlpatterns = [
    path('', views.index, name='booking'),
    path('room_photos', views.room_photos, name='room_photos'),
    path('scrollanimation', views.scroll_animation, name='scroll_animation'),
]
