"""
Canal en tiempo real de un documento. Es delgado como una vista: los permisos
salen siempre de documents/services.py (documentos_visibles / obtener_nivel),
al conectar y en cada mensaje.

Códigos de cierre:
  4401 -> sin token, token inválido o vencido.
  4404 -> el documento no existe, está eliminado, es de otro espacio o ya no
          tienes acceso (mismo criterio de aislamiento que el 404 de REST).

Mensajes del cliente: latido, pedir_turno, liberar_turno, editar.
Mensajes del servidor: conectado, presencia, turno, turno_ocupado, error.
"""

import time

from channels.generic.websocket import AsyncJsonWebsocketConsumer

from . import estado_vivo
from .middleware_jwt import SUBPROTOCOLO
from .models import PermisoDocumento
from .services import (
    PermisoInsuficiente,
    detectar_turno_vencido,
    liberar_turno,
    nivel_alcanza,
    nivel_en_documento,
    pedir_turno,
    presentes_en_documento,
    renovar_turno,
    ttl_presencia,
    turno_vigente,
)

CIERRE_NO_AUTENTICADO = 4401
CIERRE_NO_ENCONTRADO = 4404


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
        await self.send_json({"tipo": "turno", "turno": await turno_vigente(self.documento_id)})

        await self._marcar_presente()
        await self._difundir_presencia()

    async def disconnect(self, code):
        if self.grupo is None:
            return
        await self.channel_layer.group_discard(self.grupo, self.channel_name)
        await estado_vivo.quitar_presencia(self.documento_id, self.scope["user"].pk, self.channel_name)
        await self._difundir_presencia()
        if await liberar_turno(self.documento_id, self.channel_name):
            await self._difundir_turno(None)

    async def receive_json(self, contenido, **kwargs):
        # En cada mensaje: token vigente y permiso vigente.
        exp = self.scope.get("jwt_exp")
        if exp is None or exp <= time.time():
            return await self.close(code=CIERRE_NO_AUTENTICADO)

        nivel = await nivel_en_documento(self.scope["user"], self.documento_id)
        if nivel is None:
            return await self.close(code=CIERRE_NO_ENCONTRADO)

        # Cualquier mensaje entrante sirve para notar que el turno venció por
        # inactividad, sin depender del temporizador del cliente.
        if await detectar_turno_vencido(self.documento_id) is not None:
            await self._difundir_turno(None)

        tipo = contenido.get("tipo") if isinstance(contenido, dict) else None
        manejador = {
            "latido": self._latido,
            "pedir_turno": self._pedir_turno,
            "liberar_turno": self._liberar_turno,
            "editar": self._editar,
        }.get(tipo)
        if manejador is None:
            return await self._error(400, "tipo_desconocido", f"Tipo de mensaje desconocido: {tipo}")
        await manejador(nivel, contenido)

    # --- Presencia -----------------------------------------------------------

    async def _latido(self, nivel, contenido):
        # El latido mantiene SOLO la presencia: nunca renueva el turno.
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

    # --- Turno de edición ------------------------------------------------------

    async def _pedir_turno(self, nivel, contenido):
        try:
            estado, turno = await pedir_turno(self.scope["user"], self.documento_id, self.channel_name, nivel)
        except PermisoInsuficiente:
            return await self._error(403, "sin_permiso", "Necesitas permiso de edición para editar.")

        if estado == "concedido":
            await self._difundir_turno(turno)
        elif estado == "ocupado":
            await self.send_json({"tipo": "turno_ocupado", "turno": turno})
        else:  # ya_tuyo
            await self.send_json({"tipo": "turno", "turno": turno})

    async def _liberar_turno(self, nivel, contenido):
        if not await liberar_turno(self.documento_id, self.channel_name):
            return await self._error(403, "sin_turno", "No tienes el turno de edición.")
        await self._difundir_turno(None)

    async def _editar(self, nivel, contenido):
        if not nivel_alcanza(nivel, PermisoDocumento.Nivel.EDICION):
            return await self._error(403, "sin_permiso", "Necesitas permiso de edición para editar.")

        estado = await renovar_turno(self.documento_id, self.channel_name)
        if estado == "vencido":
            return await self._error(409, "turno_vencido", "Tu turno de edición venció por inactividad.")
        if estado == "ajeno":
            return await self._error(409, "sin_turno", "No tienes el turno de edición.")
        # Paso 6: retransmitir el contenido a los demás y actualizar el borrador.

    async def _difundir_turno(self, turno):
        await self.channel_layer.group_send(self.grupo, {"type": "turno", "turno": turno})

    async def turno(self, evento):
        await self.send_json({"tipo": "turno", "turno": evento["turno"]})

    # --- Utilidades -------------------------------------------------------------

    async def _error(self, codigo, motivo, detalle):
        await self.send_json({"tipo": "error", "codigo": codigo, "motivo": motivo, "detalle": detalle})

    async def _rechazar(self, codigo):
        protocolos = self.scope.get("subprotocols") or []
        subprotocolo = SUBPROTOCOLO if SUBPROTOCOLO in protocolos else None
        await self.accept(subprotocol=subprotocolo)
        await self.close(code=codigo)
