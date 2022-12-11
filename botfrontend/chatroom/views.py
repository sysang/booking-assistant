import re

from django.conf import settings
from django.shortcuts import render
from django.template.response import TemplateResponse

from services.booking_service import request_room_list_by_hotel


def index(request):
    response = TemplateResponse(request, 'chatroom/index.html', {
        'socketUrl': settings.CHAT_SERVER['socketUrl'],
        'protocol': settings.CHAT_SERVER['protocol'],
        'propsInboxIdentifier': settings.CHAT_SERVER['protocolOptions']['inboxIdentifier'],
        'propsChatwootAPIUrl': settings.CHAT_SERVER['protocolOptions']['chatwootAPIUrl'],
    })

    return response

def room_photos(request):
    hotel_id = request.GET.get('hoid')
    room_id = request.GET.get('roid')
    checkin_date = request.GET.get('chkin')
    checkout_date = request.GET.get('chkout')
    images = []

    room_list = request_room_list_by_hotel(hotel_id=hotel_id, checkin_date=checkin_date, checkout_date=checkout_date)

    if len(room_list) > 0:
        room_list = room_list[0].get('rooms', {})
        room = room_list.get(room_id)

        if room:
            for photo in room.get('photos', []):
                photo_url = photo.get('url_original')
                if photo_url:
                    images.append(photo_url)


    return TemplateResponse(request, 'chatroom/room_photos.html', {'images': images})


def scroll_animation(request):
    return TemplateResponse(request, 'chatroom/scroll_animation.html')
