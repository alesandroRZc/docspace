from rest_framework import serializers
from .models import Documento, VersionDocumento

class DocumentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Documento
        fields = ["id", "espacio", "titulo", "fecha_creacion", "fecha_actualizacion"]
    
class VersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = VersionDocumento
        fields = ["id", "numero_version", "contenido", "autor", "fecha_creacion", "restaurada_desde"]


class GuardarVersionSerializer(serializers.Serializer):
    contenido = serializers.CharField(allow_blank=True)