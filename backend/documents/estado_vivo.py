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

Turno de edición: string "doc:{id}:turno" con TTL
  valor = JSON {usuario_id, nombre, canal, version_base}
  Se toma con SET NX EX. Solo se renueva con renovar_turno (que el canal llama
  únicamente ante un "editar"); si nadie edita, Redis lo expira solo.
Marcador "doc:{id}:turno:anunciado": recuerda que hubo un turno anunciado,
  para detectar que venció (Redis borra la clave del turno sin avisar).
Todas las operaciones del turno son scripts Lua: atómicas aunque haya varios
procesos atendiendo el mismo documento.
"""

import json
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


# --- Turno de edición ---------------------------------------------------------

ANUNCIO_TTL = 24 * 60 * 60  # el marcador solo debe sobrevivir al turno


def _claves_turno(documento_id):
    return [f"doc:{documento_id}:turno", f"doc:{documento_id}:turno:anunciado"]


# Toma el turno si está libre. Devuelve el turno vigente (el propio o el ajeno).
_TOMAR = """
redis.call('SET', KEYS[1], ARGV[1], 'NX', 'EX', ARGV[2])
local actual = redis.call('GET', KEYS[1])
if actual == ARGV[1] then
  redis.call('SET', KEYS[2], ARGV[1], 'EX', ARGV[3])
end
return actual
"""

# Renueva el TTL solo si el turno es de este canal.
_RENOVAR = """
local actual = redis.call('GET', KEYS[1])
if not actual then return 'vencido' end
if cjson.decode(actual)['canal'] ~= ARGV[1] then return 'ajeno' end
redis.call('EXPIRE', KEYS[1], ARGV[2])
return 'renovado'
"""

# Comparar y borrar: solo el canal dueño puede liberar.
_LIBERAR = """
local actual = redis.call('GET', KEYS[1])
if not actual or cjson.decode(actual)['canal'] ~= ARGV[1] then return 0 end
redis.call('DEL', KEYS[1], KEYS[2])
return 1
"""

# Si el turno ya no existe pero estaba anunciado, venció: consumir el marcador
# (una sola conexión lo recibe) y devolver quién lo tenía.
_DETECTAR_VENCIDO = """
if redis.call('EXISTS', KEYS[1]) == 1 then return false end
return redis.call('GETDEL', KEYS[2])
"""


def _decodificar(valor):
    return json.loads(valor) if valor else None


async def tomar_turno(documento_id, datos, ttl):
    async with _conexion() as r:
        actual = await r.eval(_TOMAR, 2, *_claves_turno(documento_id), json.dumps(datos), ttl, ANUNCIO_TTL)
    return _decodificar(actual)


async def renovar_turno(documento_id, canal, ttl):
    """Devuelve 'renovado', 'ajeno' (lo tiene otro) o 'vencido' (no hay turno)."""
    async with _conexion() as r:
        return await r.eval(_RENOVAR, 2, *_claves_turno(documento_id), canal, ttl)


async def liberar_turno(documento_id, canal):
    async with _conexion() as r:
        return bool(await r.eval(_LIBERAR, 2, *_claves_turno(documento_id), canal))


async def detectar_turno_vencido(documento_id):
    async with _conexion() as r:
        return _decodificar(await r.eval(_DETECTAR_VENCIDO, 2, *_claves_turno(documento_id)))


async def turno_actual(documento_id):
    async with _conexion() as r:
        return _decodificar(await r.get(_claves_turno(documento_id)[0]))
