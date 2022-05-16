from django.shortcuts import render
from django.template.response import TemplateResponse


def index(request):
    response = TemplateResponse(request, 'chatroom/index.html', {})

    return response
