from .models import BitacoraAuditoria


def registrar_evento(espacio, usuario, accion, tipo_recurso, recurso_id, detalles=None):
    return BitacoraAuditoria.objects.create(
        espacio=espacio,
        usuario=usuario,
        accion=accion,
        tipo_recurso=tipo_recurso,
        recurso_id=recurso_id,
        detalles=detalles or {},
    )