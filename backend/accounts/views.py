from rest_framework import generics
from rest_framework.permissions import AllowAny
from .serializers import RegistroSerializer, UsuarioSerializer

class RegistroView(generics.CreateAPIView):
    serializer_class = RegistroSerializer
    permission_classes = [AllowAny]
    
class MeView(generics.RetrieveAPIView):
    serializer_class = UsuarioSerializer

    def get_object(self):
        return self.request.user