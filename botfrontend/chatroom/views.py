from django.shortcuts import render
from django.template.response import TemplateResponse


def index(request):
    response = TemplateResponse(request, 'chatroom/index.html', {})

    return response

def room_photos(request):
    images = request.GET.values()

    return TemplateResponse(request, 'chatroom/room_photos.html', {'images': images})
