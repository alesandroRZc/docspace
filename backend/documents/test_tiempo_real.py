import time
from datetime import timedelta

import pytest
from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from channels_redis.core import RedisChannelLayer
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from config.asgi import application
from documents import estado_vivo
from documents.models import Documento, PermisoDocumento
from workspaces.models import EspacioTrabajo, MiembroEspacio

Usuario = get_user_model()
ORIGEN = (b"origin", b"http://localhost:5173")


def test_channel_layer_redis_ida_y_vuelta():
    capa = get_channel_layer()
    # Debe ser Redis, no la capa en memoria: el estado tiene que poder
    # compartirse entre procesos.
    assert isinstance(capa, RedisChannelLayer)

    async def ida_y_vuelta():
        canal = await capa.new_channel()
        await capa.send(canal, {"type": "prueba", "texto": "hola"})
        return await capa.receive(canal)

    mensaje = async_to_sync(ida_y_vuelta)()

    assert mensaje == {"type": "prueba", "texto": "hola"}


# --- Utilidades -------------------------------------------------------------

def crear_usuario(email, tipo="COLABORADOR"):
    return Usuario.objects.create_user(email=email, username=email, password="Clave12345", nombre=email.split("@")[0], tipo_cuenta=tipo)


def token_de(usuario):
    return str(AccessToken.for_user(usuario))


def comunicador(documento_id, token=None, origen=ORIGEN):
    subprotocolos = ["access_token", token] if token is not None else []
    return WebsocketCommunicator(
        application,
        f"/ws/documents/{documento_id}/",
        headers=[origen],
        subprotocols=subprotocolos,
    )


async def conectar(documento_id, token=None):
    """Devuelve (comunicador, subprotocolo aceptado, primer mensaje recibido)."""
    ws = comunicador(documento_id, token)
    conectado, subprotocolo = await ws.connect()
    assert conectado
    return ws, subprotocolo, await ws.receive_output()


@pytest.fixture
def escenario():
    gestor = crear_usuario("gestor@x.com", "GESTOR")
    lector = crear_usuario("lector@x.com")
    espacio = EspacioTrabajo.objects.create(gestor=gestor, nombre="Espacio A")
    MiembroEspacio.objects.create(espacio=espacio, usuario=lector)
    doc = Documento.objects.create(espacio=espacio, creador=gestor, titulo="Doc A")
    PermisoDocumento.objects.create(documento=doc, usuario=lector, nivel="LECTURA")

    gestor_b = crear_usuario("gestorb@x.com", "GESTOR")
    espacio_b = EspacioTrabajo.objects.create(gestor=gestor_b, nombre="Espacio B")
    doc_b = Documento.objects.create(espacio=espacio_b, creador=gestor_b, titulo="Doc B")

    return {"gestor": gestor, "lector": lector, "doc": doc, "doc_b": doc_b}


async def recibir_tipo(ws, tipo):
    """Lee mensajes JSON hasta encontrar uno del tipo pedido."""
    while True:
        mensaje = await ws.receive_json_from()
        if mensaje["tipo"] == tipo:
            return mensaje


async def esperar_cierre(ws):
    """Descarta mensajes hasta recibir el cierre del servidor."""
    while True:
        salida = await ws.receive_output()
        if salida["type"] == "websocket.close":
            return salida


def assert_cierre(salida, codigo):
    assert salida == {"type": "websocket.close", "code": codigo}


# --- Conexión ---------------------------------------------------------------

@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("token", [None, "no-es-un-jwt"])
def test_sin_token_o_token_invalido_cierra_4401(escenario, token):
    async def probar():
        ws, _, salida = await conectar(escenario["doc"].id, token)
        assert_cierre(salida, 4401)
        await ws.disconnect()

    async_to_sync(probar)()


@pytest.mark.django_db(transaction=True)
def test_token_vencido_cierra_4401(escenario):
    acceso = AccessToken.for_user(escenario["gestor"])
    acceso.set_exp(from_time=timezone.now() - timedelta(hours=2), lifetime=timedelta(minutes=1))

    async def probar():
        ws, _, salida = await conectar(escenario["doc"].id, str(acceso))
        assert_cierre(salida, 4401)
        await ws.disconnect()

    async_to_sync(probar)()


@pytest.mark.django_db(transaction=True)
def test_refresh_token_en_lugar_de_access_cierra_4401(escenario):
    # Un refresh token es un JWT válido y firmado, pero no sirve para
    # autenticar: solo el access token. Si se dejara de validar el tipo
    # (p. ej. usando UntypedToken), esta prueba conectaría y fallaría.
    refresh = str(RefreshToken.for_user(escenario["gestor"]))

    async def probar():
        ws, _, salida = await conectar(escenario["doc"].id, refresh)
        assert_cierre(salida, 4401)
        await ws.disconnect()

    async_to_sync(probar)()


@pytest.mark.django_db(transaction=True)
def test_origen_no_permitido_es_rechazado(escenario):
    # Token válido del Gestor sobre su propio documento: lo único que falla es
    # el Origin. Si se quitara AllowedHostsOriginValidator, conectaría.
    token = token_de(escenario["gestor"])

    async def probar():
        ws = comunicador(escenario["doc"].id, token, origen=(b"origin", b"http://sitio-malo.com"))
        conectado, _ = await ws.connect()
        await ws.disconnect()
        return conectado

    assert async_to_sync(probar)() is False


@pytest.mark.django_db(transaction=True)
def test_documento_de_otro_espacio_cierra_4404(escenario):
    token = token_de(escenario["gestor"])

    async def probar():
        ws, _, salida = await conectar(escenario["doc_b"].id, token)
        assert_cierre(salida, 4404)
        await ws.disconnect()

    async_to_sync(probar)()


@pytest.mark.django_db(transaction=True)
def test_documento_eliminado_cierra_4404(escenario):
    doc = escenario["doc"]
    doc.eliminado_en = timezone.now()
    doc.save(update_fields=["eliminado_en"])
    token = token_de(escenario["gestor"])

    async def probar():
        ws, _, salida = await conectar(doc.id, token)
        assert_cierre(salida, 4404)
        await ws.disconnect()

    async_to_sync(probar)()


@pytest.mark.django_db(transaction=True)
def test_lector_conecta_y_el_servidor_no_devuelve_el_token(escenario):
    token = token_de(escenario["lector"])

    async def probar():
        ws, subprotocolo, _ = await conectar(escenario["doc"].id, token)
        assert subprotocolo == "access_token"
        await ws.disconnect()
        return subprotocolo

    assert token not in async_to_sync(probar)()


@pytest.mark.django_db(transaction=True)
def test_gestor_conecta_con_su_nivel(escenario):
    token = token_de(escenario["gestor"])

    async def probar():
        ws = comunicador(escenario["doc"].id, token)
        conectado, _ = await ws.connect()
        mensaje = await ws.receive_json_from()
        await ws.disconnect()
        return conectado, mensaje

    conectado, mensaje = async_to_sync(probar)()

    assert conectado
    assert mensaje == {"tipo": "conectado", "nivel": "ADMINISTRACION"}


# --- Verificación en cada mensaje ------------------------------------------

@pytest.mark.django_db(transaction=True)
def test_permiso_revocado_cierra_en_el_siguiente_mensaje(escenario):
    token = token_de(escenario["lector"])
    quitar_permiso = database_sync_to_async(
        lambda: PermisoDocumento.objects.filter(usuario=escenario["lector"]).delete()
    )

    async def probar():
        ws = comunicador(escenario["doc"].id, token)
        await ws.connect()
        await recibir_tipo(ws, "conectado")
        await quitar_permiso()
        await ws.send_json_to({"tipo": "cualquiera"})
        salida = await esperar_cierre(ws)
        await ws.disconnect()
        return salida

    assert_cierre(async_to_sync(probar)(), 4404)


@pytest.mark.django_db(transaction=True)
def test_mensaje_desconocido_responde_error_sin_cerrar(escenario):
    token = token_de(escenario["gestor"])

    async def probar():
        ws = comunicador(escenario["doc"].id, token)
        await ws.connect()
        await recibir_tipo(ws, "conectado")
        await ws.send_json_to({"tipo": "inventado"})
        respuesta = await recibir_tipo(ws, "error")
        await ws.disconnect()
        return respuesta

    respuesta = async_to_sync(probar)()

    assert respuesta["codigo"] == 400


# --- Presencia --------------------------------------------------------------

async def abrir(documento_id, usuario):
    """Conecta y consume el 'conectado' y la primera 'presencia'."""
    ws = comunicador(documento_id, token_de(usuario))
    conectado, _ = await ws.connect()
    assert conectado
    await recibir_tipo(ws, "conectado")
    primera = await recibir_tipo(ws, "presencia")
    return ws, primera


def nombres(mensaje):
    return [u["nombre"] for u in mensaje["usuarios"]]


@pytest.mark.django_db(transaction=True)
def test_dos_conexiones_se_ven_entre_si(escenario):
    doc, gestor, lector = escenario["doc"], escenario["gestor"], escenario["lector"]

    async def probar():
        ws_a, primera_a = await abrir(doc.id, gestor)
        ws_b, primera_b = await abrir(doc.id, lector)
        aviso_a = await recibir_tipo(ws_a, "presencia")
        await ws_a.disconnect()
        await ws_b.disconnect()
        return primera_a, primera_b, aviso_a

    primera_a, primera_b, aviso_a = async_to_sync(probar)()

    assert nombres(primera_a) == ["gestor"]
    assert nombres(primera_b) == ["gestor", "lector"]
    assert nombres(aviso_a) == ["gestor", "lector"]
    assert aviso_a["usuarios"][0] == {"id": str(gestor.id), "nombre": "gestor"}


@pytest.mark.django_db(transaction=True)
def test_al_desconectar_desaparece_de_la_presencia(escenario):
    doc = escenario["doc"]

    async def probar():
        ws_a, _ = await abrir(doc.id, escenario["gestor"])
        ws_b, _ = await abrir(doc.id, escenario["lector"])
        await recibir_tipo(ws_a, "presencia")  # entra B
        await ws_b.disconnect()
        aviso = await recibir_tipo(ws_a, "presencia")  # sale B
        await ws_a.disconnect()
        return aviso

    assert nombres(async_to_sync(probar)()) == ["gestor"]


@pytest.mark.django_db(transaction=True)
def test_latido_purga_entrada_vencida_y_avisa(escenario):
    doc, lector = escenario["doc"], escenario["lector"]

    async def probar():
        ws, _ = await abrir(doc.id, escenario["gestor"])
        # Una pestaña del lector que dejó de latir hace 100 s (cerrada sin aviso).
        await estado_vivo.registrar_presencia(doc.id, lector.pk, "canal-muerto", ttl=30, ahora=time.time() - 100)
        await ws.send_json_to({"tipo": "latido"})
        aviso = await recibir_tipo(ws, "presencia")
        await ws.disconnect()
        return aviso

    assert nombres(async_to_sync(probar)()) == ["gestor"]


@pytest.mark.django_db(transaction=True)
def test_dos_pestanas_del_mismo_usuario_cuentan_una_vez(escenario):
    doc, gestor = escenario["doc"], escenario["gestor"]

    async def probar():
        pestana_1, _ = await abrir(doc.id, gestor)
        pestana_2, con_dos = await abrir(doc.id, gestor)
        await recibir_tipo(pestana_1, "presencia")  # entra la pestaña 2
        await pestana_2.disconnect()
        tras_cerrar_una = await recibir_tipo(pestana_1, "presencia")  # sale la pestaña 2
        await pestana_1.disconnect()
        return con_dos, tras_cerrar_una

    con_dos, tras_cerrar_una = async_to_sync(probar)()

    assert nombres(con_dos) == ["gestor"]
    # Cerrar una pestaña no lo saca: la otra sigue abierta.
    assert nombres(tras_cerrar_una) == ["gestor"]


@pytest.mark.django_db(transaction=True)
def test_latido_con_permiso_revocado_cierra_4404(escenario):
    doc, lector = escenario["doc"], escenario["lector"]
    quitar_permiso = database_sync_to_async(
        lambda: PermisoDocumento.objects.filter(usuario=lector).delete()
    )

    async def probar():
        ws, _ = await abrir(doc.id, lector)
        await quitar_permiso()
        await ws.send_json_to({"tipo": "latido"})
        salida = await esperar_cierre(ws)
        await ws.disconnect()
        return salida

    assert_cierre(async_to_sync(probar)(), 4404)
