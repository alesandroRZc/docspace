from django.urls import path

from .consumers import DocumentoConsumer

websocket_urlpatterns = [
    path("ws/documents/<uuid:documento_id>/", DocumentoConsumer.as_asgi()),
]
