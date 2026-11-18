from rest_framework import serializers
from .models import Documento, VersionDocumento, PermisoDocumento

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
    
class PermisoSerializer(serializers.ModelSerializer):
    class Meta:
        model = PermisoDocumento
        fields = ["id", "documento", "usuario", "nivel"]


class AsignarPermisoSerializer(serializers.Serializer):
    email = serializers.EmailField()
    nivel = serializers.ChoiceField(choices=PermisoDocumento.Nivel.choices)
    
class CompararSerializer(serializers.Serializer):
    a = serializers.IntegerField(min_value=1)
    b = serializers.IntegerField(min_value=1)