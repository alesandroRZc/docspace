import uuid
from django.conf import settings
from django.db import models

# Create your models here.
class BitacoraAuditoria(models.Model):
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    espacio = models.ForeignKey("workspaces.EspacioTrabajo",on_delete=models.PROTECT,related_name="eventos_auditoria")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name="eventos_auditoria")
    accion = models.CharField(max_length=50)
    tipo_recurso = models.CharField(max_length=50)
    recurso_id = models.UUIDField()
    detalles = models.JSONField(default=dict)
    fecha_evento = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_evento"]
        
    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Una Bitácora de Auditoría registrada no se puede modificar.")
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        raise ValueError("Una Bitácora de Auditoría registrada no se puede eliminar.")