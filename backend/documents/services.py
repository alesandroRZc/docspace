from django.db.models import Q
from django.db import transaction
from .models import Documento, PermisoDocumento, VersionDocumento
from workspaces.models import MiembroEspacio
from audit.services import registrar_evento
import difflib


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

  
        
def tiene_nivel(usuario, documento, nivel_minimo):
    nivel = obtener_nivel(usuario, documento)
    if nivel is None:
        return False
    return JERARQUIA[nivel] >= JERARQUIA[nivel_minimo]



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

def comparar_versiones(version_a, version_b):
    lineas = difflib.unified_diff(
        version_a.contenido.splitlines(),
        version_b.contenido.splitlines(),
        fromfile=f"v{version_a.numero_version}",
        tofile=f"v{version_b.numero_version}",
        lineterm="",
    )
    return list(lineas)
    