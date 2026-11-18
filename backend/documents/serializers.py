from rest_framework import serializers
from .models import Documento

class DocumentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Documento
        fields = ["id", "espacio", "titulo", "fecha_creacion", "fecha_actualizacion"]