"""
Configuración ASGI del proyecto.

ProtocolTypeRouter separa el tráfico por protocolo. Por ahora solo enruta
HTTP (la API REST de siempre); la ruta "websocket" se agrega en el paso
de conexión en tiempo real.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Inicializar Django antes de importar nada que use modelos.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter  # noqa: E402

application = ProtocolTypeRouter({
    "http": django_asgi_app,
})
