from django.db.models import Q
from rest_framework import generics
from documents.services import documentos_visibles
from .models import BitacoraAuditoria
from .serializers import BitacoraSerializer


class BitacoraListView(generics.ListAPIView):
    serializer_class = BitacoraSerializer

    def get_queryset(self):
        usuario = self.request.user
        ids_visibles = documentos_visibles(usuario).values_list("id", flat=True)
        return BitacoraAuditoria.objects.filter(
            Q(espacio__gestor=usuario)
            | Q(tipo_recurso="DOCUMENTO", recurso_id__in=ids_visibles)
        )