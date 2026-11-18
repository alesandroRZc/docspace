from rest_framework import serializers
from .models import Usuario

class RegistroSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = Usuario
        fields = ["id", "email", "username", "nombre", "tipo_cuenta", "password"]
        read_only_fields = ["id"]

    def create(self, validated_data):
        return Usuario.objects.create_user(**validated_data)