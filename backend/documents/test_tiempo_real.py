import asyncio
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

from audit.models import BitacoraAuditoria
from config.asgi import application
from documents import estado_vivo
from documents.models import Documento, PermisoDocumento, VersionDocumento
from documents.services import guardar_version
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
    editor = crear_usuario("editor@x.com")
    MiembroEspacio.objects.create(espacio=espacio, usuario=editor)
    PermisoDocumento.objects.create(documento=doc, usuario=editor, nivel="EDICION")

    gestor_b = crear_usuario("gestorb@x.com", "GESTOR")
    espacio_b = EspacioTrabajo.objects.create(gestor=gestor_b, nombre="Espacio B")
    doc_b = Documento.objects.create(espacio=espacio_b, creador=gestor_b, titulo="Doc B")

    return {"gestor": gestor, "lector": lector, "editor": editor, "doc": doc, "doc_b": doc_b}


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


# --- Turno de edición ---------------------------------------------------------

def quien(turno_msg):
    return turno_msg["turno"]["nombre"] if turno_msg["turno"] else None


@pytest.mark.django_db(transaction=True)
def test_editor_obtiene_el_turno_y_todos_lo_ven(escenario):
    doc = escenario["doc"]

    async def probar():
        ws_editor, _ = await abrir(doc.id, escenario["editor"])
        ws_lector, _ = await abrir(doc.id, escenario["lector"])
        await ws_editor.send_json_to({"tipo": "pedir_turno"})
        visto_por_editor = await recibir_tipo(ws_editor, "turno")
        visto_por_lector = await recibir_tipo(ws_lector, "turno")
        await ws_editor.disconnect()
        await ws_lector.disconnect()
        return visto_por_editor, visto_por_lector

    visto_por_editor, visto_por_lector = async_to_sync(probar)()

    assert quien(visto_por_editor) == "editor"
    assert quien(visto_por_lector) == "editor"
    assert "canal" not in visto_por_lector["turno"]  # no se filtra el canal interno


@pytest.mark.django_db(transaction=True)
def test_quien_se_conecta_ve_el_turno_vigente(escenario):
    doc = escenario["doc"]

    async def probar():
        ws_editor, _ = await abrir(doc.id, escenario["editor"])
        await ws_editor.send_json_to({"tipo": "pedir_turno"})
        await recibir_tipo(ws_editor, "turno")
        ws_nuevo = comunicador(doc.id, token_de(escenario["gestor"]))
        await ws_nuevo.connect()
        inicial = await recibir_tipo(ws_nuevo, "turno")
        await ws_nuevo.disconnect()
        await ws_editor.disconnect()
        return inicial

    assert quien(async_to_sync(probar)()) == "editor"


@pytest.mark.django_db(transaction=True)
def test_segundo_editor_recibe_ocupado_con_el_nombre(escenario):
    doc = escenario["doc"]

    async def probar():
        ws_a, _ = await abrir(doc.id, escenario["editor"])
        ws_b, _ = await abrir(doc.id, escenario["gestor"])
        await ws_a.send_json_to({"tipo": "pedir_turno"})
        await recibir_tipo(ws_b, "turno")
        await ws_b.send_json_to({"tipo": "pedir_turno"})
        respuesta = await recibir_tipo(ws_b, "turno_ocupado")
        await ws_a.disconnect()
        await ws_b.disconnect()
        return respuesta

    assert quien(async_to_sync(probar)()) == "editor"


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("mensaje", ["pedir_turno", "editar"])
def test_lector_no_puede_pedir_turno_ni_editar(escenario, mensaje):
    doc = escenario["doc"]

    async def probar():
        ws, _ = await abrir(doc.id, escenario["lector"])
        await ws.send_json_to({"tipo": mensaje})
        error = await recibir_tipo(ws, "error")
        turno = await estado_vivo.turno_actual(doc.id)
        await ws.disconnect()
        return error, turno

    error, turno = async_to_sync(probar)()

    assert error["codigo"] == 403
    assert turno is None


@pytest.mark.django_db(transaction=True)
def test_quien_no_es_dueno_no_puede_liberar(escenario):
    doc = escenario["doc"]

    async def probar():
        ws_a, _ = await abrir(doc.id, escenario["editor"])
        ws_b, _ = await abrir(doc.id, escenario["gestor"])
        await ws_a.send_json_to({"tipo": "pedir_turno"})
        await recibir_tipo(ws_b, "turno")
        await ws_b.send_json_to({"tipo": "liberar_turno"})
        error = await recibir_tipo(ws_b, "error")
        turno = await estado_vivo.turno_actual(doc.id)
        await ws_a.disconnect()
        await ws_b.disconnect()
        return error, turno

    error, turno = async_to_sync(probar)()

    assert error["codigo"] == 403
    assert turno["nombre"] == "editor"


@pytest.mark.django_db(transaction=True)
def test_dueno_libera_y_todos_ven_turno_libre(escenario):
    doc = escenario["doc"]

    async def probar():
        ws_a, _ = await abrir(doc.id, escenario["editor"])
        ws_b, _ = await abrir(doc.id, escenario["gestor"])
        await ws_a.send_json_to({"tipo": "pedir_turno"})
        await recibir_tipo(ws_b, "turno")
        await ws_a.send_json_to({"tipo": "liberar_turno"})
        aviso = await recibir_tipo(ws_b, "turno")
        await ws_a.disconnect()
        await ws_b.disconnect()
        return aviso

    assert quien(async_to_sync(probar)()) is None


@pytest.mark.django_db(transaction=True)
def test_al_desconectarse_el_dueno_el_turno_queda_libre(escenario):
    doc = escenario["doc"]

    async def probar():
        ws_a, _ = await abrir(doc.id, escenario["editor"])
        ws_b, _ = await abrir(doc.id, escenario["gestor"])
        await ws_a.send_json_to({"tipo": "pedir_turno"})
        await recibir_tipo(ws_b, "turno")
        await ws_a.disconnect()
        aviso = await recibir_tipo(ws_b, "turno")
        await ws_b.disconnect()
        return aviso

    assert quien(async_to_sync(probar)()) is None


@pytest.mark.django_db(transaction=True)
def test_un_latido_sin_ediciones_no_renueva_el_turno(escenario, settings):
    # TTL de 2 s. El dueño late al segundo 1: si el latido renovara, el turno
    # duraría hasta el segundo 3 y a los 2.3 s seguiría ocupado.
    settings.TURNO_TTL = 2
    doc = escenario["doc"]

    async def probar():
        ws_a, _ = await abrir(doc.id, escenario["editor"])
        ws_b, _ = await abrir(doc.id, escenario["gestor"])
        await ws_a.send_json_to({"tipo": "pedir_turno"})
        await recibir_tipo(ws_a, "turno")  # su propio turno concedido
        await recibir_tipo(ws_b, "turno")

        await asyncio.sleep(1.0)
        await ws_a.send_json_to({"tipo": "latido"})
        await asyncio.sleep(1.3)

        await ws_b.send_json_to({"tipo": "pedir_turno"})
        libre_visto_por_a = await recibir_tipo(ws_a, "turno")
        nuevo_visto_por_a = await recibir_tipo(ws_a, "turno")
        await ws_a.disconnect()
        await ws_b.disconnect()
        return libre_visto_por_a, nuevo_visto_por_a

    libre, nuevo = async_to_sync(probar)()

    assert quien(libre) is None        # el servidor anunció el vencimiento
    assert quien(nuevo) == "gestor"    # y otro editor pudo tomarlo


@pytest.mark.django_db(transaction=True)
def test_editar_del_dueno_si_renueva_el_turno(escenario, settings):
    # Mismo reloj que la prueba anterior, pero con un "editar" en vez de latido.
    settings.TURNO_TTL = 2
    doc = escenario["doc"]

    async def probar():
        ws_a, _ = await abrir(doc.id, escenario["editor"])
        ws_b, _ = await abrir(doc.id, escenario["gestor"])
        await ws_a.send_json_to({"tipo": "pedir_turno"})
        await recibir_tipo(ws_b, "turno")

        await asyncio.sleep(1.0)
        await ws_a.send_json_to({"tipo": "editar", "contenido": "hola"})
        await asyncio.sleep(1.3)

        await ws_b.send_json_to({"tipo": "pedir_turno"})
        respuesta = await recibir_tipo(ws_b, "turno_ocupado")
        await ws_a.disconnect()
        await ws_b.disconnect()
        return respuesta

    assert quien(async_to_sync(probar)()) == "editor"


@pytest.mark.django_db(transaction=True)
def test_editar_con_el_turno_vencido_responde_turno_vencido(escenario, settings):
    settings.TURNO_TTL = 1
    doc = escenario["doc"]

    async def probar():
        ws, _ = await abrir(doc.id, escenario["editor"])
        await ws.send_json_to({"tipo": "pedir_turno"})
        await recibir_tipo(ws, "turno")
        await asyncio.sleep(1.3)
        await ws.send_json_to({"tipo": "editar", "contenido": "hola"})
        error = await recibir_tipo(ws, "error")
        await ws.disconnect()
        return error

    error = async_to_sync(probar)()

    assert error["codigo"] == 409
    assert error["motivo"] == "turno_vencido"


# --- Edición en vivo y guardado al terminar el turno ------------------------

def versiones_de(doc):
    return list(VersionDocumento.objects.filter(documento=doc).order_by("numero_version"))


def eventos(doc, accion):
    return list(BitacoraAuditoria.objects.filter(recurso_id=doc.id, accion=accion))


async def pendientes(ws, espera=0.3):
    """Todos los mensajes JSON que llegan en `espera` segundos."""
    mensajes = []
    while not await ws.receive_nothing(timeout=espera):
        mensajes.append(await ws.receive_json_from())
    return mensajes


async def con_turno(doc, usuario):
    """Abre una conexión y toma el turno."""
    ws, _ = await abrir(doc.id, usuario)
    await ws.send_json_to({"tipo": "pedir_turno"})
    await recibir_tipo(ws, "turno")
    return ws


@pytest.mark.django_db(transaction=True)
def test_editar_llega_a_los_demas_y_no_crea_version(escenario):
    doc = escenario["doc"]

    async def probar():
        ws_editor = await con_turno(doc, escenario["editor"])
        ws_lector, _ = await abrir(doc.id, escenario["lector"])
        for texto in ["H", "Ho", "Hola"]:
            await ws_editor.send_json_to({"tipo": "editar", "contenido": texto})
        recibidos = [(await recibir_tipo(ws_lector, "cambio"))["contenido"] for _ in range(3)]
        pendientes_editor = await pendientes(ws_editor)
        versiones_antes_de_cerrar = await database_sync_to_async(versiones_de)(doc)
        await ws_lector.disconnect()
        await ws_editor.disconnect()
        return recibidos, pendientes_editor, versiones_antes_de_cerrar

    recibidos, pendientes_editor, versiones = async_to_sync(probar)()

    assert recibidos == ["H", "Ho", "Hola"]
    # El editor no recibe su propio cambio de vuelta.
    assert "cambio" not in [m["tipo"] for m in pendientes_editor], pendientes_editor
    assert versiones == []  # ninguna versión por tecla mientras edita


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("infractor, observador, codigo", [
    ("lector", "gestor", 403),   # sin permiso de edición
    ("gestor", "lector", 409),   # con permiso, pero sin el turno
])
def test_editar_rechazado_no_se_retransmite(escenario, infractor, observador, codigo):
    doc = escenario["doc"]

    async def probar():
        ws_dueno = await con_turno(doc, escenario["editor"])
        ws_infractor, _ = await abrir(doc.id, escenario[infractor])
        ws_observador, _ = await abrir(doc.id, escenario[observador])
        await ws_infractor.send_json_to({"tipo": "editar", "contenido": "intruso"})
        error = await recibir_tipo(ws_infractor, "error")
        await ws_dueno.send_json_to({"tipo": "editar", "contenido": "legitimo"})
        primero = await recibir_tipo(ws_observador, "cambio")
        borrador = await estado_vivo.leer_borrador(doc.id)
        for ws in (ws_dueno, ws_infractor, ws_observador):
            await ws.disconnect()
        return error, primero, borrador

    error, primero, borrador = async_to_sync(probar)()

    assert error["codigo"] == codigo
    assert primero["contenido"] == "legitimo"   # "intruso" nunca llegó
    assert borrador["contenido"] == "legitimo"


@pytest.mark.django_db(transaction=True)
def test_editar_demasiado_grande_responde_413(escenario, settings):
    settings.EDITAR_MAX_CARACTERES = 10
    doc = escenario["doc"]

    async def probar():
        ws_editor = await con_turno(doc, escenario["editor"])
        ws_lector, _ = await abrir(doc.id, escenario["lector"])
        await ws_editor.send_json_to({"tipo": "editar", "contenido": "corto"})
        await recibir_tipo(ws_lector, "cambio")
        await ws_editor.send_json_to({"tipo": "editar", "contenido": "x" * 11})
        error = await recibir_tipo(ws_editor, "error")
        nada_mas = await ws_lector.receive_nothing(timeout=0.3)
        borrador = await estado_vivo.leer_borrador(doc.id)
        await ws_editor.disconnect()
        await ws_lector.disconnect()
        return error, nada_mas, borrador

    error, nada_mas, borrador = async_to_sync(probar)()

    assert error["codigo"] == 413
    assert nada_mas                          # no se retransmitió
    assert borrador["contenido"] == "corto"  # ni se guardó en el borrador


@pytest.mark.django_db(transaction=True)
def test_quien_se_conecta_a_mitad_recibe_el_borrador_en_vivo(escenario):
    doc = escenario["doc"]

    async def probar():
        ws_editor = await con_turno(doc, escenario["editor"])
        await ws_editor.send_json_to({"tipo": "editar", "contenido": "a medio escribir"})
        await asyncio.sleep(0.2)
        ws_nuevo = comunicador(doc.id, token_de(escenario["lector"]))
        await ws_nuevo.connect()
        cambio = await recibir_tipo(ws_nuevo, "cambio")
        await ws_nuevo.disconnect()
        await ws_editor.disconnect()
        return cambio

    cambio = async_to_sync(probar)()

    assert cambio["contenido"] == "a medio escribir"
    assert cambio["nombre"] == "editor"


@pytest.mark.django_db(transaction=True)
def test_liberar_crea_exactamente_una_version_y_todos_la_ven(escenario):
    doc, editor = escenario["doc"], escenario["editor"]

    async def probar():
        ws_editor = await con_turno(doc, editor)
        ws_lector, _ = await abrir(doc.id, escenario["lector"])
        for texto in ["Uno", "Uno dos", "Uno dos tres"]:
            await ws_editor.send_json_to({"tipo": "editar", "contenido": texto})
        await ws_editor.send_json_to({"tipo": "liberar_turno"})
        aviso = await recibir_tipo(ws_lector, "version_guardada")
        turno = await estado_vivo.turno_actual(doc.id)
        borrador = await estado_vivo.leer_borrador(doc.id)
        await ws_editor.disconnect()
        await ws_lector.disconnect()
        return aviso, turno, borrador

    aviso, turno, borrador = async_to_sync(probar)()

    versiones = versiones_de(doc)
    assert [v.contenido for v in versiones] == ["Uno dos tres"]
    assert versiones[0].autor == editor
    assert aviso == {"tipo": "version_guardada", "numero_version": 1, "autor": "editor"}
    assert len(eventos(doc, "EDITAR_DOCUMENTO")) == 1
    assert turno is None and borrador is None


@pytest.mark.django_db(transaction=True)
def test_liberar_sin_cambios_no_crea_version(escenario):
    doc = escenario["doc"]

    async def probar():
        ws = await con_turno(doc, escenario["editor"])
        await ws.send_json_to({"tipo": "liberar_turno"})
        libre = await recibir_tipo(ws, "turno")
        await ws.disconnect()
        return libre

    assert quien(async_to_sync(probar)()) is None
    assert versiones_de(doc) == []


@pytest.mark.django_db(transaction=True)
def test_conflicto_manual_conserva_turno_y_borrador_y_se_resuelve_confirmando(escenario):
    doc, editor, gestor = escenario["doc"], escenario["editor"], escenario["gestor"]
    guardar_por_rest = database_sync_to_async(lambda: guardar_version(doc, gestor, "cambio de otro"))

    async def probar():
        ws = await con_turno(doc, editor)  # base: versión 0
        await ws.send_json_to({"tipo": "editar", "contenido": "mi texto"})
        await asyncio.sleep(0.2)
        await guardar_por_rest()           # alguien guarda la v1 por REST
        await ws.send_json_to({"tipo": "liberar_turno"})
        conflicto = await recibir_tipo(ws, "conflicto")
        turno = await estado_vivo.turno_actual(doc.id)
        borrador = await estado_vivo.leer_borrador(doc.id)
        # El editor revisa la v1 y confirma que quiere guardar encima de ella.
        await ws.send_json_to({"tipo": "liberar_turno", "version_base": conflicto["version_actual"]})
        guardada = await recibir_tipo(ws, "version_guardada")
        await ws.disconnect()
        return conflicto, turno, borrador, guardada

    conflicto, turno, borrador, guardada = async_to_sync(probar)()

    assert conflicto["version_actual"] == 1
    assert conflicto["contenido_actual"] == "cambio de otro"
    assert turno["nombre"] == "editor"           # conserva el turno
    assert borrador["contenido"] == "mi texto"   # y su texto
    assert guardada["numero_version"] == 2
    assert [v.contenido for v in versiones_de(doc)] == ["cambio de otro", "mi texto"]
    assert len(eventos(doc, "CONFLICTO_VERSION")) == 1


@pytest.mark.django_db(transaction=True)
def test_descartar_libera_sin_guardar_y_queda_en_bitacora(escenario):
    doc = escenario["doc"]

    async def probar():
        ws = await con_turno(doc, escenario["editor"])
        await ws.send_json_to({"tipo": "editar", "contenido": "no me sirve"})
        await ws.send_json_to({"tipo": "liberar_turno", "descartar": True})
        libre = await recibir_tipo(ws, "turno")
        borrador = await estado_vivo.leer_borrador(doc.id)
        await ws.disconnect()
        return libre, borrador

    libre, borrador = async_to_sync(probar)()

    assert quien(libre) is None and borrador is None
    assert versiones_de(doc) == []
    assert len(eventos(doc, "DESCARTAR_BORRADOR")) == 1


@pytest.mark.django_db(transaction=True)
def test_desconexion_con_cambios_pendientes_guarda_la_version(escenario):
    doc = escenario["doc"]

    async def probar():
        ws_editor = await con_turno(doc, escenario["editor"])
        ws_lector, _ = await abrir(doc.id, escenario["lector"])
        await ws_editor.send_json_to({"tipo": "editar", "contenido": "cerré la pestaña"})
        await recibir_tipo(ws_lector, "cambio")
        await ws_editor.disconnect()
        aviso = await recibir_tipo(ws_lector, "version_guardada")
        await ws_lector.disconnect()
        return aviso

    assert async_to_sync(probar)()["numero_version"] == 1
    assert [v.contenido for v in versiones_de(doc)] == ["cerré la pestaña"]


@pytest.mark.django_db(transaction=True)
def test_turno_vencido_con_la_pestana_abierta_guarda_el_borrador(escenario, settings):
    settings.TURNO_TTL = 1
    doc, editor = escenario["doc"], escenario["editor"]

    async def probar():
        ws_editor = await con_turno(doc, editor)
        ws_lector, _ = await abrir(doc.id, escenario["lector"])
        await ws_editor.send_json_to({"tipo": "editar", "contenido": "me fui a tomar café"})
        await recibir_tipo(ws_lector, "cambio")
        await asyncio.sleep(1.3)
        # Ningún temporizador del cliente: el editor solo sigue latiendo.
        await ws_editor.send_json_to({"tipo": "latido"})
        aviso = await recibir_tipo(ws_lector, "version_guardada")
        await ws_editor.disconnect()
        await ws_lector.disconnect()
        return aviso

    aviso = async_to_sync(probar)()

    assert aviso == {"tipo": "version_guardada", "numero_version": 1, "autor": "editor"}
    assert versiones_de(doc)[0].autor == editor


@pytest.mark.django_db(transaction=True)
def test_borrador_huerfano_se_guarda_al_conectarse_alguien(escenario, settings):
    # Simula una caída del proceso: queda un turno (que vence) y su borrador,
    # sin ninguna conexión viva que se entere.
    settings.TURNO_TTL = 1
    doc, editor = escenario["doc"], escenario["editor"]
    datos = {"usuario_id": str(editor.pk), "nombre": "editor", "canal": "canal-caido", "version_base": 0}

    async def probar():
        await estado_vivo.tomar_turno(doc.id, datos, ttl=1)
        await estado_vivo.aplicar_edicion(doc.id, "canal-caido", "texto rescatado", ttl=1)
        await asyncio.sleep(1.3)
        ws, _ = await abrir(doc.id, escenario["gestor"])
        await ws.disconnect()

    async_to_sync(probar)()

    versiones = versiones_de(doc)
    assert [v.contenido for v in versiones] == ["texto rescatado"]
    assert versiones[0].autor == editor


@pytest.mark.django_db(transaction=True)
def test_conflicto_automatico_conserva_el_texto_en_la_bitacora(escenario):
    doc, editor, gestor = escenario["doc"], escenario["editor"], escenario["gestor"]
    guardar_por_rest = database_sync_to_async(lambda: guardar_version(doc, gestor, "cambio de otro"))

    async def probar():
        ws_editor = await con_turno(doc, editor)
        ws_lector, _ = await abrir(doc.id, escenario["lector"])
        await ws_editor.send_json_to({"tipo": "editar", "contenido": "mi texto"})
        await recibir_tipo(ws_lector, "cambio")
        await guardar_por_rest()
        await ws_editor.disconnect()       # guardado automático -> conflicto
        aviso = await recibir_tipo(ws_lector, "borrador_en_conflicto")
        await ws_lector.disconnect()
        return aviso

    aviso = async_to_sync(probar)()

    assert aviso["autor"] == "editor"
    assert [v.contenido for v in versiones_de(doc)] == ["cambio de otro"]  # no tapó la otra
    conservado = eventos(doc, "BORRADOR_EN_CONFLICTO")
    assert len(conservado) == 1
    assert conservado[0].detalles["contenido"] == "mi texto"
    assert conservado[0].usuario == editor


@pytest.mark.django_db(transaction=True)
def test_sin_permiso_al_guardar_automatico_se_descarta(escenario):
    doc, editor = escenario["doc"], escenario["editor"]
    quitar_permiso = database_sync_to_async(
        lambda: PermisoDocumento.objects.filter(usuario=editor).delete()
    )

    async def probar():
        ws = await con_turno(doc, editor)
        await ws.send_json_to({"tipo": "editar", "contenido": "ya no debería guardarse"})
        await asyncio.sleep(0.2)
        await quitar_permiso()
        await ws.disconnect()

    async_to_sync(probar)()

    assert versiones_de(doc) == []
    descartes = eventos(doc, "BORRADOR_DESCARTADO")
    assert len(descartes) == 1
    assert "contenido" not in descartes[0].detalles
