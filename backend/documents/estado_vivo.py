"""
Estado efímero del tiempo real, guardado en Redis (nunca en memoria del
proceso, para que funcione con varios procesos y sobreviva a reinicios).

Este módulo solo sabe de claves, puntuaciones y TTL. No decide permisos ni
reglas de negocio: eso vive en documents/services.py.

Presencia: sorted set "doc:{id}:presencia"
  miembro    = "{usuario_id}|{channel_name}"  (una entrada por pestaña)
  puntuación = timestamp del último latido
Las entradas más viejas que el TTL se purgan al leer, así una pestaña cerrada
sin aviso desaparece sola.
"""

import time
from contextlib import asynccontextmanager

import redis.asyncio as redis
from django.conf import settings


@asynccontextmanager
async def _conexion():
    # Una conexión por operación: evita compartir un cliente entre event loops
    # distintos (Daphne, async_to_sync en las pruebas).
    cliente = redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        yield cliente
    finally:
        await cliente.aclose()


def _clave_presencia(documento_id):
    return f"doc:{documento_id}:presencia"


def _miembro(usuario_id, canal):
    return f"{usuario_id}|{canal}"


async def registrar_presencia(documento_id, usuario_id, canal, ttl, ahora=None):
    """Alta o latido de una pestaña. La clave entera expira si nadie late."""
    ahora = time.time() if ahora is None else ahora
    clave = _clave_presencia(documento_id)
    async with _conexion() as r:
        await r.zadd(clave, {_miembro(usuario_id, canal): ahora})
        await r.expire(clave, ttl * 2)


async def quitar_presencia(documento_id, usuario_id, canal):
    async with _conexion() as r:
        await r.zrem(_clave_presencia(documento_id), _miembro(usuario_id, canal))


async def usuarios_presentes(documento_id, ttl, ahora=None):
    """Devuelve (ids de usuario presentes, cuántas entradas vencidas se purgaron)."""
    ahora = time.time() if ahora is None else ahora
    clave = _clave_presencia(documento_id)
    async with _conexion() as r:
        purgadas = await r.zremrangebyscore(clave, "-inf", ahora - ttl)
        miembros = await r.zrange(clave, 0, -1)
    return {miembro.split("|", 1)[0] for miembro in miembros}, purgadas
