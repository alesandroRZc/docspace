from rest_framework import serializers
from .models import BitacoraAuditoria


class BitacoraSerializer(serializers.ModelSerializer):
    class Meta:
        model = BitacoraAuditoria
        fields = ["id", "espacio", "usuario", "accion", "tipo_recurso", "recurso_id", "detalles", "fecha_evento"]
        