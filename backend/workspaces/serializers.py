from rest_framework import serializers
from .models import EspacioTrabajo, MiembroEspacio

class EspacioSerializer(serializers.ModelSerializer):
    class Meta:
        model = EspacioTrabajo
        fields = ["id", "nombre", "fecha_creacion"]
        read_only_fields = ["id", "fecha_creacion"]
        
class MiembroSerializer(serializers.ModelSerializer):
    class Meta:
        model = MiembroEspacio
        fields = ["id", "espacio", "usuario", "fecha_ingreso"]


class AgregarMiembroSerializer(serializers.Serializer):
    email = serializers.EmailField()