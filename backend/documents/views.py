from django.db import transaction
from rest_framework import generics
from rest_framework.exceptions import NotFound, PermissionDenied
from workspaces.models import MiembroEspacio
from .serializers import DocumentoSerializer
from .services import documentos_visibles, guardar_version


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