from channels.db import database_sync_to_async
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.db import transaction
from .models import Documento, PermisoDocumento, VersionDocumento
from . import estado_vivo
from workspaces.models import MiembroEspacio
from audit.services import registrar_evento
import difflib

Usuario = get_user_model()


JERARQUIA = {
    "LECTURA": 1,
    "EDICION": 2,
    "ADMINISTRACION": 3,
}

def obtener_nivel(usuario, documento):
    if documento.eliminado_en is not None:
        return None
    if documento.espacio.gestor == usuario:
        return PermisoDocumento.Nivel.ADMINISTRACION
    
    # Aislamiento: aunque exista un PermisoDocumento, si el usuario ya no es
    # miembro del espacio no tiene acceso. Ser miembro es requisito previo.
    if not MiembroEspacio.objects.filter(espacio=documento.espacio, usuario=usuario).exists():
        return None
     
    permiso = PermisoDocumento.objects.filter(documento=documento, usuario=usuario).first()
    if permiso is not None:
        return  permiso.nivel
    return None

  
        
def nivel_alcanza(nivel, nivel_minimo):
    if nivel is None:
        return False
    return JERARQUIA[nivel] >= JERARQUIA[nivel_minimo]


def tiene_nivel(usuario, documento, nivel_minimo):
    return nivel_alcanza(obtener_nivel(usuario, documento), nivel_minimo)


@database_sync_to_async
def nivel_en_documento(usuario, documento_id):
    """Nivel del usuario sobre el documento, o None si no lo ve (para el canal en tiempo real)."""
    documento = documentos_visibles(usuario).select_related("espacio").filter(pk=documento_id).first()
    if documento is None:
        return None
    return obtener_nivel(usuario, documento)



def documentos_visibles(usuario):
    return Documento.objects.filter(
        eliminado_en__isnull=True
    ).filter(
        Q(espacio__gestor=usuario)
        | Q(permisos__usuario=usuario, espacio__miembros__usuario=usuario)
    ).distinct()

class ConflictoVersion(Exception):
    """El contenido se editó sobre una versión que ya no es la última."""

    def __init__(self, version_actual, contenido_actual):
        super().__init__(f"El documento ya está en la versión {version_actual}.")
        self.version_actual = version_actual
        self.contenido_actual = contenido_actual


def guardar_version(documento, autor, contenido, restaurada_desde=None, version_base=None):
    """
    Crea la siguiente versión del documento.

    Control optimista: si se indica `version_base` y no coincide con la última
    versión, no se crea nada y se lanza ConflictoVersion. El conflicto queda en
    la bitácora (fuera de la transacción del guardado, para que la excepción no
    revierta el registro; quien llame no debe envolver esto en otro atomic si
    quiere conservar ese evento). Sin `version_base` se comporta como siempre.
    """
    with transaction.atomic():
        documento = Documento.objects.select_for_update().get(pk=documento.pk)

        ultimo = VersionDocumento.objects.filter(documento=documento).order_by("-numero_version").first()
        actual = ultimo.numero_version if ultimo is not None else 0

        if version_base is None or version_base == actual:
            siguiente = actual + 1
            version = VersionDocumento.objects.create(documento=documento,autor=autor,contenido=contenido,numero_version=siguiente,restaurada_desde=restaurada_desde,)

            accion = "RESTAURAR_VERSION" if restaurada_desde else "EDITAR_DOCUMENTO"
            registrar_evento(
                documento.espacio,
                autor,
                accion,
                "DOCUMENTO",
                documento.id,
                {"numero_version": siguiente},
            )
            return version

    # Conflicto: la transacción ya se cerró sin crear ninguna versión.
    registrar_evento(
        documento.espacio,
        autor,
        "CONFLICTO_VERSION",
        "DOCUMENTO",
        documento.id,
        {"version_base": version_base, "version_actual": actual},
    )
    raise ConflictoVersion(actual, ultimo.contenido if ultimo is not None else "")

def ttl_presencia():
    return getattr(settings, "PRESENCIA_TTL", 30)


@database_sync_to_async
def _datos_de_usuarios(ids):
    usuarios = Usuario.objects.filter(pk__in=ids).order_by("nombre")
    return [{"id": str(u.id), "nombre": u.nombre} for u in usuarios]


async def presentes_en_documento(documento_id):
    """
    Lista de usuarios conectados al documento (una vez por usuario aunque
    tenga varias pestañas), con su nombre. También indica si se purgaron
    entradas vencidas, para que el canal avise a los demás.
    """
    ids, purgadas = await estado_vivo.usuarios_presentes(documento_id, ttl_presencia())
    return await _datos_de_usuarios(ids), purgadas


# --- Turno de edición (un editor a la vez) -----------------------------------

class PermisoInsuficiente(Exception):
    pass


def ttl_turno():
    return getattr(settings, "TURNO_TTL", 30)


def turno_publico(turno):
    """Lo que ven los demás: quién edita (sin el canal interno)."""
    if turno is None:
        return None
    return {"usuario_id": turno["usuario_id"], "nombre": turno["nombre"]}


@database_sync_to_async
def _numero_version_actual(documento_id):
    ultima = VersionDocumento.objects.filter(documento_id=documento_id).order_by("-numero_version").first()
    return ultima.numero_version if ultima is not None else 0


async def pedir_turno(usuario, documento_id, canal, nivel):
    """
    Devuelve (estado, turno_publico) con estado:
      "concedido" -> el turno es ahora de este canal
      "ya_tuyo"   -> este canal ya lo tenía (NO renueva el TTL)
      "ocupado"   -> lo tiene otro; turno_publico dice quién
    Requiere EDICION.
    """
    if not nivel_alcanza(nivel, PermisoDocumento.Nivel.EDICION):
        raise PermisoInsuficiente()

    datos = {
        "usuario_id": str(usuario.pk),
        "nombre": usuario.nombre,
        "canal": canal,
        "version_base": await _numero_version_actual(documento_id),
    }
    vigente = await estado_vivo.tomar_turno(documento_id, datos, ttl_turno())

    if vigente is None or vigente["canal"] != canal:
        return "ocupado", turno_publico(vigente)
    if vigente == datos:
        return "concedido", turno_publico(vigente)
    return "ya_tuyo", turno_publico(vigente)


async def turno_vigente(documento_id):
    return turno_publico(await estado_vivo.turno_actual(documento_id))


# --- Edición en vivo y guardado al terminar el turno ------------------------

class ContenidoDemasiadoGrande(Exception):
    pass


def max_caracteres_edicion():
    return getattr(settings, "EDITAR_MAX_CARACTERES", 200_000)


async def aplicar_edicion(documento_id, canal, contenido):
    """
    Edición en vivo del dueño del turno: renueva el turno y actualiza el
    borrador. NO crea versión. Es lo único que renueva el turno (el latido no).
    Devuelve 'renovado', 'ajeno' o 'vencido'.
    """
    if len(contenido) > max_caracteres_edicion():
        raise ContenidoDemasiadoGrande()
    return await estado_vivo.aplicar_edicion(documento_id, canal, contenido, ttl_turno())


async def borrador_en_vivo(documento_id):
    """Texto que se está editando ahora mismo (para quien se conecta a mitad)."""
    turno = await estado_vivo.turno_actual(documento_id)
    borrador = await estado_vivo.leer_borrador(documento_id)
    if turno is None or borrador is None or borrador["canal"] != turno["canal"]:
        return None
    return {"contenido": borrador["contenido"], **turno_publico(turno)}


@database_sync_to_async
def _guardar_borrador(documento_id, borrador, automatico):
    """
    Convierte el borrador en versión con guardar_version() y control optimista.
    Devuelve un dict con "estado": guardada | sin_cambios | conflicto | sin_permiso.
    """
    documento = Documento.objects.select_related("espacio").get(pk=documento_id)
    autor = Usuario.objects.filter(pk=borrador["usuario_id"]).first()
    resultado = {"autor": borrador["nombre"]}

    # El permiso se vuelve a comprobar al guardar: pudo cambiar desde la edición.
    if autor is None or not tiene_nivel(autor, documento, PermisoDocumento.Nivel.EDICION):
        registrar_evento(documento.espacio, autor, "BORRADOR_DESCARTADO", "DOCUMENTO", documento.id,
                         {"motivo": "sin_permiso", "version_base": borrador["version_base"]})
        return {**resultado, "estado": "sin_permiso"}

    ultima = documento.versiones.first()
    if (ultima.contenido if ultima is not None else "") == borrador["contenido"]:
        return {**resultado, "estado": "sin_cambios"}

    try:
        version = guardar_version(documento, autor, borrador["contenido"], version_base=borrador["version_base"])
    except ConflictoVersion as conflicto:
        if automatico:
            # Nadie puede decidir ahora: el texto se conserva en la bitácora en
            # vez de tapar la otra versión o perderse.
            registrar_evento(documento.espacio, autor, "BORRADOR_EN_CONFLICTO", "DOCUMENTO", documento.id, {
                "version_base": borrador["version_base"],
                "version_actual": conflicto.version_actual,
                "contenido": borrador["contenido"],
            })
        return {**resultado, "estado": "conflicto",
                "version_actual": conflicto.version_actual, "contenido_actual": conflicto.contenido_actual}

    return {**resultado, "estado": "guardada", "numero_version": version.numero_version}


@database_sync_to_async
def _registrar_descarte(documento_id, borrador):
    documento = Documento.objects.select_related("espacio").get(pk=documento_id)
    autor = Usuario.objects.filter(pk=borrador["usuario_id"]).first()
    registrar_evento(documento.espacio, autor, "DESCARTAR_BORRADOR", "DOCUMENTO", documento.id,
                     {"version_base": borrador["version_base"]})


async def terminar_turno(documento_id, canal, *, version_confirmada=None, descartar=False, automatico=False):
    """
    Libera el turno de este canal guardando antes su borrador como versión.

    - Manual (botón Guardar): ante un conflicto NO libera nada; el editor
      conserva turno y borrador y decide (reintentar confirmando la versión que
      ya vio con `version_confirmada`, o `descartar`).
    - Automático (desconexión): ante un conflicto el texto queda en la bitácora
      y el turno se libera.
    Devuelve un dict con "estado" (además de los de _guardar_borrador:
    sin_turno | descartado).
    """
    turno = await estado_vivo.turno_actual(documento_id)
    if turno is None or turno["canal"] != canal:
        return {"estado": "sin_turno"}

    borrador = await estado_vivo.leer_borrador(documento_id)
    if borrador is None or borrador["canal"] != canal:
        resultado = {"estado": "sin_cambios", "autor": turno["nombre"]}
    elif descartar:
        await _registrar_descarte(documento_id, borrador)
        resultado = {"estado": "descartado", "autor": turno["nombre"]}
    else:
        if version_confirmada is not None:
            borrador["version_base"] = version_confirmada
        resultado = await _guardar_borrador(documento_id, borrador, automatico)
        if resultado["estado"] == "conflicto" and not automatico:
            return resultado

    await estado_vivo.liberar_turno(documento_id, canal)
    return resultado


async def procesar_turno_vencido(documento_id):
    """
    Si el turno venció sin liberarse (inactividad o caída del proceso), guarda
    su borrador a nombre de su autor. Devuelve None si no venció nada; si no,
    el resultado del guardado. Solo una conexión lo procesa (Lua atómico).
    """
    detectado = await estado_vivo.detectar_turno_vencido(documento_id)
    if detectado is None:
        return None
    anterior, borrador = detectado
    if borrador is None or borrador["canal"] != anterior["canal"]:
        return {"estado": "sin_cambios", "autor": anterior["nombre"]}
    resultado = await _guardar_borrador(documento_id, borrador, automatico=True)
    await estado_vivo.borrar_borrador(documento_id, borrador["canal"])
    return resultado


def comparar_versiones(version_a, version_b):
    lineas = difflib.unified_diff(
        version_a.contenido.splitlines(),
        version_b.contenido.splitlines(),
        fromfile=f"v{version_a.numero_version}",
        tofile=f"v{version_b.numero_version}",
        lineterm="",
    )
    return list(lineas)
    