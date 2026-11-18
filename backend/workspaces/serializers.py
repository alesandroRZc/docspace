from rest_framework import serializers
from .models import EspacioTrabajo

class EspacioSerializer(serializers.ModelSerializer):
    class Meta:
        model = EspacioTrabajo
        fields = ["id", "nombre", "fecha_creacion"]
        read_only_fields = ["id", "fecha_creacion"]