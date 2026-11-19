"""
Configuración ASGI del proyecto.

ProtocolTypeRouter separa el tráfico por protocolo:
- "http": la API REST de siempre.
- "websocket": el canal en tiempo real de los documentos. Valida el origen
  contra ALLOWED_HOSTS y autentica con el JWT enviado como subprotocolo.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Inicializar Django antes de importar nada que use modelos.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

from documents.middleware_jwt import JWTSubprotocoloMiddleware  # noqa: E402
from documents.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        JWTSubprotocoloMiddleware(URLRouter(websocket_urlpatterns))
    ),
})
