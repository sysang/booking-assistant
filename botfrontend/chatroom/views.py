import re

from django.shortcuts import render
from django.template.response import TemplateResponse


def index(request):
    response = TemplateResponse(request, 'chatroom/index.html', {})

    return response

def room_photos(request):
    p = re.compile('https\:\/\/.+')
    images = []
    for param in request.GET.values():
        m = p.fullmatch(param)
        if m:
            images.append(m.group())

    return TemplateResponse(request, 'chatroom/room_photos.html', {'images': images})
