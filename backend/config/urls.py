"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView , TokenRefreshView
from accounts.views import RegistroView
from documents.views import DocumentoListView, DocumentoDetailView, GuardarVersionView, VersionListView, AsignarPermisoView, CompararVersionesView,  RestaurarVersionView
from workspaces.views import EspacioListCreateView, AgregarMiembroView
from audit.views import BitacoraListView


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/schema/', SpectacularAPIView.as_view(), name="schema"),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name="schema"),name="swagger-ui"),
    path('api/auth/login/', TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name="token_refresh"),
    path('api/auth/register/', RegistroView.as_view(), name="register"),
    path('api/documents/', DocumentoListView.as_view(), name="documento-list"),
    path('api/documents/<uuid:pk>/', DocumentoDetailView.as_view(), name="documento-detail"),
    path("api/workspaces/", EspacioListCreateView.as_view(), name="espacio-list"),
    path("api/documents/<uuid:pk>/save/", GuardarVersionView.as_view(), name="documento-save"),
    path("api/documents/<uuid:pk>/versions/", VersionListView.as_view(), name="documento-versions"),
    path("api/workspaces/<uuid:pk>/members/", AgregarMiembroView.as_view(), name="espacio-members"),
    path("api/documents/<uuid:pk>/permissions/", AsignarPermisoView.as_view(), name="documento-permissions"),
    path("api/documents/<uuid:pk>/compare/", CompararVersionesView.as_view(), name="documento-compare"),
    path("api/documents/<uuid:pk>/versions/<int:numero>/restore/", RestaurarVersionView.as_view(), name="documento-restore"),
    path("api/audit/", BitacoraListView.as_view(), name="bitacora-list"),
]
