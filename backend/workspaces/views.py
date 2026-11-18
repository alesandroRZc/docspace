from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from .models import EspacioTrabajo, MiembroEspacio
from .serializers import EspacioSerializer

class EspacioListCreateView(generics.ListCreateAPIView):
    serializer_class = EspacioSerializer

    def get_queryset(self):
        return EspacioTrabajo.objects.filter(miembros__usuario=self.request.user)

    def perform_create(self, serializer):
        if self.request.user.tipo_cuenta != "GESTOR":
            raise PermissionDenied("Solo un Gestor puede crear espacios de trabajo.")
        espacio = serializer.save(gestor=self.request.user)
        MiembroEspacio.objects.create(espacio=espacio, usuario=self.request.user)