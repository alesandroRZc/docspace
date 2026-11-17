import uuid
from django.conf import settings
from django.db import models

# Create your models here.

    

class EspacioTrabajo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gestor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="espacios_gestionados")
    nombre = models.CharField("nombre", max_length=150)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    
class MiembroEspacio(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    espacio = models.ForeignKey(EspacioTrabajo, on_delete=models.CASCADE, related_name="miembros")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="membresias")
    fecha_ingreso = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        constraints = [
        models.UniqueConstraint(fields=["espacio", "usuario"] , name="miembro_unico_por_espacio"),
        ]

