from django.shortcuts import render
from rest_framework import generics
from .serializers import DocumentoSerializer
from .services import documentos_visibles

# Create your views here.

class DocumentoListView(generics.ListAPIView):
    serializer_class = DocumentoSerializer

    def get_queryset(self):
        return documentos_visibles(self.request.user)

class DocumentoDetailView(generics.RetrieveAPIView):
    serializer_class = DocumentoSerializer

    def get_queryset(self):
        return documentos_visibles(self.request.user)
