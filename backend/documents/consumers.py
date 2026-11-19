"""
Canal en tiempo real de un documento. Es delgado como una vista: los permisos
salen siempre de documents/services.py (documentos_visibles / obtener_nivel),
al conectar y en cada mensaje.

Códigos de cierre:
  4401 -> sin token, token inválido o vencido.
  4404 -> el documento no existe, está eliminado, es de otro espacio o ya no
          tienes acceso (mismo criterio de aislamiento que el 404 de REST).
"""

import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from . import estado_vivo
from .middleware_jwt import SUBPROTOCOLO
from .services import documentos_visibles, obtener_nivel, presentes_en_documento, ttl_presencia

CIERRE_NO_AUTENTICADO = 4401
CIERRE_NO_ENCONTRADO = 4404


@database_sync_to_async
def nivel_en_documento(usuario, documento_id):
    documento = documentos_visibles(usuario).select_related("espacio").filter(pk=documento_id).first()
    if documento is None:
        return None
    return obtener_nivel(usuario, documento)


class DocumentoConsumer(AsyncJsonWebsocketConsumer):
    grupo = None

    async def connect(self):
        self.documento_id = str(self.scope["url_route"]["kwargs"]["documento_id"])
        usuario = self.scope.get("user")

        # El permiso se decide ANTES de aceptar. Si se rechaza, se acepta solo
        # para poder entregar un código de cierre propio (un rechazo en el
        # handshake llega al navegador como 1006 genérico) y se cierra sin
        # enviar ningún dato.
        if usuario is None or not usuario.is_authenticated:
            return await self._rechazar(CIERRE_NO_AUTENTICADO)

        nivel = await nivel_en_documento(usuario, self.documento_id)
        if nivel is None:
            return await self._rechazar(CIERRE_NO_ENCONTRADO)

        self.grupo = f"documento_{self.documento_id}"
        await self.channel_layer.group_add(self.grupo, self.channel_name)
        await self.accept(subprotocol=SUBPROTOCOLO)
        await self.send_json({"tipo": "conectado", "nivel": nivel})

        await self._marcar_presente()
        await self._difundir_presencia()

    async def disconnect(self, code):
        if self.grupo is None:
            return
        await self.channel_layer.group_discard(self.grupo, self.channel_name)
        await estado_vivo.quitar_presencia(self.documento_id, self.scope["user"].pk, self.channel_name)
        await self._difundir_presencia()

    async def receive_json(self, contenido, **kwargs):
        # En cada mensaje: token vigente y permiso vigente.
        exp = self.scope.get("jwt_exp")
        if exp is None or exp <= time.time():
            return await self.close(code=CIERRE_NO_AUTENTICADO)

        nivel = await nivel_en_documento(self.scope["user"], self.documento_id)
        if nivel is None:
            return await self.close(code=CIERRE_NO_ENCONTRADO)

        tipo = contenido.get("tipo") if isinstance(contenido, dict) else None
        if tipo == "latido":
            return await self._latido()
        # Los mensajes de turno y edición llegan en los pasos 5 y 6.
        await self.send_json({"tipo": "error", "codigo": 400, "detalle": f"Tipo de mensaje desconocido: {tipo}"})

    # --- Presencia -----------------------------------------------------------

    async def _latido(self):
        # El latido mantiene SOLO la presencia (no renueva el turno de edición).
        await self._marcar_presente()
        usuarios, purgadas = await presentes_en_documento(self.documento_id)
        if purgadas:
            # Alguien desapareció sin cerrar la conexión: avisar a todos.
            await self._enviar_presencia_al_grupo(usuarios)

    async def _marcar_presente(self):
        await estado_vivo.registrar_presencia(
            self.documento_id, self.scope["user"].pk, self.channel_name, ttl_presencia()
        )

    async def _difundir_presencia(self):
        usuarios, _ = await presentes_en_documento(self.documento_id)
        await self._enviar_presencia_al_grupo(usuarios)

    async def _enviar_presencia_al_grupo(self, usuarios):
        await self.channel_layer.group_send(self.grupo, {"type": "presencia", "usuarios": usuarios})

    async def presencia(self, evento):
        await self.send_json({"tipo": "presencia", "usuarios": evento["usuarios"]})

    async def _rechazar(self, codigo):
        protocolos = self.scope.get("subprotocols") or []
        subprotocolo = SUBPROTOCOLO if SUBPROTOCOLO in protocolos else None
        await self.accept(subprotocol=subprotocolo)
        await self.close(code=codigo)
