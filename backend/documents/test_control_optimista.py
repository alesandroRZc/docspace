import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from audit.models import BitacoraAuditoria
from documents.models import Documento, VersionDocumento
from documents.services import ConflictoVersion, guardar_version
from documents.models import PermisoDocumento
from workspaces.models import EspacioTrabajo, MiembroEspacio

Usuario = get_user_model()


@pytest.fixture
def gestor():
    return Usuario.objects.create_user(email="g@x.com", username="g", password="Clave12345", nombre="G", tipo_cuenta="GESTOR")


@pytest.fixture
def doc(gestor):
    espacio = EspacioTrabajo.objects.create(gestor=gestor, nombre="Espacio A")
    documento = Documento.objects.create(espacio=espacio, creador=gestor, titulo="Doc 1")
    guardar_version(documento, gestor, "v1")
    return documento


@pytest.mark.django_db
def test_base_vigente_guarda(doc, gestor):
    version = guardar_version(doc, gestor, "v2", version_base=1)

    assert version.numero_version == 2


@pytest.mark.django_db
def test_base_vieja_lanza_conflicto_sin_crear_version(doc, gestor):
    guardar_version(doc, gestor, "v2", version_base=1)

    with pytest.raises(ConflictoVersion) as error:
        guardar_version(doc, gestor, "texto sobre v1", version_base=1)

    assert error.value.version_actual == 2
    assert error.value.contenido_actual == "v2"
    assert VersionDocumento.objects.filter(documento=doc).count() == 2
    evento = BitacoraAuditoria.objects.get(recurso_id=doc.id, accion="CONFLICTO_VERSION")
    assert evento.detalles == {"version_base": 1, "version_actual": 2}


@pytest.mark.django_db
def test_endpoint_responde_409_ante_base_vieja(doc, gestor):
    cliente = APIClient()
    cliente.force_authenticate(user=gestor)

    r1 = cliente.post(f"/api/documents/{doc.id}/save/", {"contenido": "A", "version_base": 1}, format="json")
    r2 = cliente.post(f"/api/documents/{doc.id}/save/", {"contenido": "B", "version_base": 1}, format="json")

    assert r1.status_code == 201
    assert r2.status_code == 409
    assert r2.json()["version_actual"] == 2
    assert r2.json()["contenido_actual"] == "A"
    assert VersionDocumento.objects.filter(documento=doc).count() == 2


@pytest.mark.django_db
def test_sin_version_base_se_comporta_como_antes(doc, gestor):
    cliente = APIClient()
    cliente.force_authenticate(user=gestor)

    r = cliente.post(f"/api/documents/{doc.id}/save/", {"contenido": "sin base"}, format="json")

    assert r.status_code == 201
    assert r.json()["numero_version"] == 2


@pytest.mark.django_db
def test_detalle_expone_version_actual(doc, gestor):
    cliente = APIClient()
    cliente.force_authenticate(user=gestor)

    r = cliente.get(f"/api/documents/{doc.id}/")

    assert r.json()["version_actual"] == 1


@pytest.mark.django_db
def test_documento_y_versiones_muestran_el_nombre_del_autor(doc, gestor):
    # La v2 la guarda otra persona: así se comprueba que autor_nombre es el
    # autor de cada versión y no el creador del documento.
    ana = Usuario.objects.create_user(email="ana@x.com", username="ana", password="Clave12345", nombre="Ana", tipo_cuenta="COLABORADOR")
    MiembroEspacio.objects.create(espacio=doc.espacio, usuario=ana)
    PermisoDocumento.objects.create(documento=doc, usuario=ana, nivel="EDICION")
    guardar_version(doc, ana, "v2")
    cliente = APIClient()
    cliente.force_authenticate(user=gestor)

    detalle = cliente.get(f"/api/documents/{doc.id}/").json()
    versiones = cliente.get(f"/api/documents/{doc.id}/versions/").json()

    assert detalle["creador_nombre"] == "G"
    assert [(v["numero_version"], v["autor_nombre"]) for v in versiones] == [(2, "Ana"), (1, "G")]
