from .models import PermisoDocumento
from workspaces.models import MiembroEspacio

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
    
    if not  MiembroEspacio.objects.filter(espacio=documento.espacio, usuario=usuario).exists():
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