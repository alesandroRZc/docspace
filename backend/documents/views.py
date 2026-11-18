from django.db import transaction
from rest_framework import generics
from rest_framework.exceptions import NotFound, PermissionDenied
from workspaces.models import MiembroEspacio
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import DocumentoSerializer, GuardarVersionSerializer, VersionSerializer, AsignarPermisoSerializer, PermisoSerializer
from .services import documentos_visibles, guardar_version, tiene_nivel
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError
from .models import PermisoDocumento

Usuario = get_user_model()


class DocumentoListView(generics.ListCreateAPIView):
    serializer_class = DocumentoSerializer

    def get_queryset(self):
        return documentos_visibles(self.request.user)

    def perform_create(self, serializer):
        usuario = self.request.user
        espacio = serializer.validated_data["espacio"]

        if not MiembroEspacio.objects.filter(espacio=espacio, usuario=usuario).exists():
            raise NotFound("Espacio no encontrado.")
        if espacio.gestor != usuario:
            raise PermissionDenied("Solo el Gestor del espacio puede crear documentos.")

        with transaction.atomic():
            documento = serializer.save(creador=usuario)
            guardar_version(documento, usuario, "")


class DocumentoDetailView(generics.RetrieveAPIView):
    serializer_class = DocumentoSerializer

    def get_queryset(self):
        return documentos_visibles(self.request.user)
    
class GuardarVersionView(APIView):
    @extend_schema(request=GuardarVersionSerializer, responses=VersionSerializer)
    def post(self, request, pk):
        documento = get_object_or_404(documentos_visibles(request.user), pk=pk)

        if not tiene_nivel(request.user, documento, "EDICION"):
            raise PermissionDenied("Necesitas permiso de edición para guardar.")

        entrada = GuardarVersionSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        version = guardar_version(documento, request.user, entrada.validated_data["contenido"])
        return Response(VersionSerializer(version).data, status=status.HTTP_201_CREATED)
    
class VersionListView(generics.ListAPIView):
    serializer_class = VersionSerializer

    def get_queryset(self):
        documento = get_object_or_404(documentos_visibles(self.request.user), pk=self.kwargs["pk"])
        return documento.versiones.all()
    
class AsignarPermisoView(APIView):
    @extend_schema(request=AsignarPermisoSerializer, responses=PermisoSerializer)
    def post(self, request, pk):
        documento = get_object_or_404(documentos_visibles(request.user), pk=pk)

        if not tiene_nivel(request.user, documento, "ADMINISTRACION"):
            raise PermissionDenied("Necesitas permiso de administración para gestionar permisos.")

        entrada = AsignarPermisoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        usuario = Usuario.objects.filter(email=entrada.validated_data["email"]).first()
        es_miembro = usuario is not None and MiembroEspacio.objects.filter(espacio=documento.espacio, usuario=usuario).exists()
        if not es_miembro:
            raise ValidationError("El usuario debe ser miembro del espacio del documento.")

        permiso, creado = PermisoDocumento.objects.update_or_create(
            documento=documento,
            usuario=usuario,
            defaults={"nivel": entrada.validated_data["nivel"]},
        )
        codigo = status.HTTP_201_CREATED if creado else status.HTTP_200_OK
        return Response(PermisoSerializer(permiso).data, status=codigo)
    
