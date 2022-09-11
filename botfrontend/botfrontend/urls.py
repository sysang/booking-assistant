"""botfrontend URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path, re_path

from django.conf.urls.static import static
from django.conf import settings

from . import views

urlpatterns = [
    path('dialogue/admin/', admin.site.urls),
    path('dialogue/accounts/', include('django.contrib.auth.urls')),
    path('dialogue/accounts/', include('registration.backends.default.urls')),

    path('dialogue/urls', views.urls, name='urls'),

    path('dialogue/booking/', include('chatroom.urls', namespace='booking')),
    path('dialogue/chatroom/', include('chatroom.urls', namespace='chatroom')),

    path('dialogue/o/', include('oauth2_provider.urls', namespace='oauth2_provider')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
