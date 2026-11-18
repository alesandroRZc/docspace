from django.db import transaction
from rest_framework import generics
from rest_framework.exceptions import NotFound, PermissionDenied
from workspaces.models import MiembroEspacio
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import DocumentoSerializer, GuardarVersionSerializer, VersionSerializer
from .services import documentos_visibles, guardar_version, tiene_nivel


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