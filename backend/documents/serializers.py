from rest_framework import serializers
from .models import Documento, VersionDocumento, PermisoDocumento
from .services import obtener_nivel

class DocumentoSerializer(serializers.ModelSerializer):
    mi_permiso = serializers.SerializerMethodField()
    contenido_actual = serializers.SerializerMethodField()

    class Meta:
        model = Documento
        fields = ["id", "espacio", "titulo", "fecha_creacion", "fecha_actualizacion", "mi_permiso", "contenido_actual"]

    def get_mi_permiso(self, obj) -> str | None:
        request = self.context.get("request")
        if request is None:
            return None
        return obtener_nivel(request.user, obj)

    def get_contenido_actual(self, obj) -> str:
        ultima = obj.versiones.first()
        if ultima is None:
            return ""
        return ultima.contenido
    
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