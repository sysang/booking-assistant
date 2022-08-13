import json

from django.urls import reverse
from django.http import HttpResponse
from django.conf import settings


def urls(request):
    base_domain_url = settings.BASE_DOMAIN_URL
    data = {'room_photos': base_domain_url + reverse('booking:room_photos')}
    response = HttpResponse(json.dumps(data), content_type="application/json")

    return response
