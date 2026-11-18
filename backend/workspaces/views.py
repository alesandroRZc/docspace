from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from .models import EspacioTrabajo, MiembroEspacio
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import AgregarMiembroSerializer, EspacioSerializer, MiembroSerializer, CrearColaboradorSerializer
from audit.services import registrar_evento
from django.db import transaction

Usuario = get_user_model()

class EspacioListCreateView(generics.ListCreateAPIView):
    serializer_class = EspacioSerializer

    def get_queryset(self):
        return EspacioTrabajo.objects.filter(miembros__usuario=self.request.user)

    def perform_create(self, serializer):
        if self.request.user.tipo_cuenta != "GESTOR":
            raise PermissionDenied("Solo un Gestor puede crear espacios de trabajo.")
        espacio = serializer.save(gestor=self.request.user)
        MiembroEspacio.objects.create(espacio=espacio, usuario=self.request.user)

class AgregarMiembroView(APIView):
    @extend_schema(request=AgregarMiembroSerializer, responses=MiembroSerializer)
    def post(self, request, pk):
        espacio = get_object_or_404(EspacioTrabajo.objects.filter(miembros__usuario=request.user), pk=pk)

        if espacio.gestor != request.user:
            raise PermissionDenied("Solo el Gestor del espacio puede agregar miembros.")

        entrada = AgregarMiembroSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        usuario = Usuario.objects.filter(email=entrada.validated_data["email"]).first()
        if usuario is None:
            raise NotFound("No existe un usuario con ese correo.")

        miembro, creado = MiembroEspacio.objects.get_or_create(espacio=espacio, usuario=usuario)
        if creado:
            registrar_evento(espacio, request.user, "AGREGAR_MIEMBRO", "USUARIO", usuario.id, {"email": usuario.email})
        codigo = status.HTTP_201_CREATED if creado else status.HTTP_200_OK
        return Response(MiembroSerializer(miembro).data, status=codigo)
    
class CrearColaboradorView(APIView):
    @extend_schema(request=CrearColaboradorSerializer, responses=MiembroSerializer)
    def post(self, request, pk):
        espacio = get_object_or_404(EspacioTrabajo.objects.filter(miembros__usuario=request.user), pk=pk)

        if espacio.gestor != request.user:
            raise PermissionDenied("Solo el Gestor del espacio puede crear colaboradores.")

        entrada = CrearColaboradorSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        with transaction.atomic():
            usuario = entrada.save(tipo_cuenta="COLABORADOR")
            miembro = MiembroEspacio.objects.create(espacio=espacio, usuario=usuario)
            registrar_evento(espacio, request.user, "CREAR_USUARIO", "USUARIO", usuario.id, {"email": usuario.email})

        return Response(MiembroSerializer(miembro).data, status=status.HTTP_201_CREATED)