from django.db.models import Q
from django.db import transaction
from .models import Documento, PermisoDocumento, VersionDocumento
from workspaces.models import MiembroEspacio
from .models import Documento, PermisoDocumento


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
    
    #Remover Not: "pruebas que realmente fallan si se rompe la lógica"
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

def guardar_version(documento, autor, contenido):
    with transaction.atomic():
        documento = Documento.objects.select_for_update().get(pk=documento.pk)

        ultimo = VersionDocumento.objects.filter(documento=documento).order_by("-numero_version").first()
        if ultimo is not None:
                siguiente = ultimo.numero_version + 1
        else:
                siguiente = 1

        version = VersionDocumento.objects.create(documento=documento, autor=autor, contenido=contenido, numero_version=siguiente)
        return version