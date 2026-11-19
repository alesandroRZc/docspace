"""
Autenticación del WebSocket con el JWT de SimpleJWT, enviado como subprotocolo.

El cliente abre: new WebSocket(url, ["access_token", "<jwt>"])
El navegador lo manda en la cabecera Sec-WebSocket-Protocol, así el token no
queda en la URL (ni en los logs de acceso). El consumer debe responder solo con
el subprotocolo "access_token", nunca con el token.

Este middleware solo identifica al usuario. Los permisos sobre el documento los
decide el consumer usando documents/services.py.
"""

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import AccessToken

SUBPROTOCOLO = "access_token"


def extraer_token(scope):
    protocolos = scope.get("subprotocols") or []
    if len(protocolos) >= 2 and protocolos[0] == SUBPROTOCOLO:
        return protocolos[1]
    return None


@database_sync_to_async
def usuario_desde_token(token):
    """Devuelve (usuario, exp). Con token ausente, inválido o vencido: (AnonymousUser, None)."""
    if not token:
        return AnonymousUser(), None
    try:
        acceso = AccessToken(token)
    except TokenError:
        return AnonymousUser(), None

    usuario = get_user_model().objects.filter(
        **{api_settings.USER_ID_FIELD: acceso[api_settings.USER_ID_CLAIM]},
        is_active=True,
    ).first()
    if usuario is None:
        return AnonymousUser(), None
    return usuario, acceso["exp"]


class JWTSubprotocoloMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        scope["user"], scope["jwt_exp"] = await usuario_desde_token(extraer_token(scope))
        return await super().__call__(scope, receive, send)
