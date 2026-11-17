import uuid
from django.conf import settings
from django.db import models

# Create your models here.
class Documento(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    espacio = models.ForeignKey("workspaces.EspacioTrabajo", on_delete=models.PROTECT, related_name="documentos")
    creador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="documentos_creados")
    titulo = models.CharField("titulo", max_length=255)
    fecha_creacion = models.DateTimeField (auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    eliminado_en = models.DateTimeField(null=True, blank=True)
    
class VersionesDocumento(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    documento = models.ForeignKey(Documento, on_delete=models.PROTECT, related_name="versiones")
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="versiones_creadas")
    contenido = models.TextField(blank=True )
    numero_version = models.PositiveBigIntegerField ("numero_version")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    restaurada_desde = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="restauraciones")
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["documento", "numero_version"], name="version_unica_por_documento"),
        ]
        ordering = ["-numero_version"]
        
    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Una version emitido no se puede modificar.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Una version emitido no se puede eliminar.")

    
class PermisoDocumento(models.Model):
    class Nivel(models.TextChoices):
            LECTURA = "LECTURA", "Lectura"
            EDICION = "EDICION", "Edición"
            ADMINISTRACION = "ADMINISTRACION", "Administración"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    documento = models.ForeignKey(Documento, on_delete=models.CASCADE, related_name="permisos")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="permisos_documentos")
    nivel = models.CharField(max_length=20, choices=Nivel.choices)
    
    class Meta:
        constraints = [
        models.UniqueConstraint(fields=["documento", "usuario"], name="permiso_unico_por_documento"),
        ]

