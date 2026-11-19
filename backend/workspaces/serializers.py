from rest_framework import serializers
from .models import EspacioTrabajo, MiembroEspacio
from accounts.serializers import RegistroSerializer

class EspacioSerializer(serializers.ModelSerializer):
    class Meta:
        model = EspacioTrabajo
        fields = ["id", "nombre", "gestor", "fecha_creacion"]
        read_only_fields = ["id", "gestor", "fecha_creacion"]
        
        
class MiembroSerializer(serializers.ModelSerializer):
    class Meta:
        model = MiembroEspacio
        fields = ["id", "espacio", "usuario", "fecha_ingreso"]


class AgregarMiembroSerializer(serializers.Serializer):
    email = serializers.EmailField()
    
class CrearColaboradorSerializer(RegistroSerializer):
    
    class Meta(RegistroSerializer.Meta):
        fields = ["id", "email", "username", "nombre", "password"]