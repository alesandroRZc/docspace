import pytest
from workspaces.models import EspacioTrabajo, MiembroEspacio
from documents.models import VersionDocumento, Documento, PermisoDocumento
from documents.services import obtener_nivel, tiene_nivel, guardar_version
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from audit.models import BitacoraAuditoria

Usuario = get_user_model()

@pytest.mark.django_db
def test_gestor_tiene_administracion():
   
    gestor = Usuario.objects.create_user(email="a@x.com", username="a", password="Clave12345", nombre="A", tipo_cuenta="GESTOR")
    espacio = EspacioTrabajo.objects.create(gestor=gestor, nombre="Espacio A")
    doc = Documento.objects.create(espacio=espacio, creador=gestor, titulo="Doc 1")

    resultado = obtener_nivel(gestor, doc) 

    assert resultado == "ADMINISTRACION"
    
@pytest.mark.django_db
def test_usuario_de_otro_espacio_no_ve_documento():
   
    gestor = Usuario.objects.create_user(email="a@x.com", username="a", password="Clave12345", nombre="A", tipo_cuenta="GESTOR")
    intruso = Usuario.objects.create_user(email= "b@x.com", username="b", password="Clave54321", nombre="B", tipo_cuenta="COLABORADOR")
    espacio = EspacioTrabajo.objects.create(gestor=gestor, nombre="Espacio A")
    doc = Documento.objects.create(espacio=espacio, creador=gestor, titulo="Doc 1")

    resultado = obtener_nivel(intruso, doc)

    assert resultado is None
    
@pytest.mark.django_db
def test_lectura_no_puede_editar():
   
    gestor = Usuario.objects.create_user(email="a@x.com", username="a", password="Clave12345", nombre="A", tipo_cuenta="GESTOR")
    espacio = EspacioTrabajo.objects.create(gestor=gestor, nombre="Espacio A")
    doc = Documento.objects.create(espacio=espacio, creador=gestor, titulo="Doc 1")
    colab = Usuario.objects.create_user(email="c@x.com", username="c", password="Clave12345", nombre="C", tipo_cuenta="COLABORADOR")
    MiembroEspacio.objects.create(espacio=espacio, usuario=colab)
    PermisoDocumento.objects.create(documento=doc, usuario=colab, nivel="LECTURA")

    resultado = tiene_nivel(colab, doc, "EDICION")

    assert resultado is False
  
@pytest.mark.django_db
def test_colaborador_con_edicion_puede_editar():
   
    gestor = Usuario.objects.create_user(email="a@x.com", username="a", password="Clave12345", nombre="A", tipo_cuenta="GESTOR")
    espacio = EspacioTrabajo.objects.create(gestor=gestor, nombre="Espacio A")
    doc = Documento.objects.create(espacio=espacio, creador=gestor, titulo="Doc 1")
    colab = Usuario.objects.create_user(email="c@x.com", username="c", password="Clave12345", nombre="C", tipo_cuenta="COLABORADOR")
    MiembroEspacio.objects.create(espacio=espacio, usuario=colab)
    PermisoDocumento.objects.create(documento=doc, usuario=colab, nivel="EDICION")

    resultado = tiene_nivel(colab, doc, "EDICION")

    assert resultado is True
    
@pytest.mark.django_db   
def test_guardar_crea_versiones_consecutivas():
    gestor = Usuario.objects.create_user(email="a@x.com", username="a", password="Clave12345", nombre="A", tipo_cuenta="GESTOR")
    espacio = EspacioTrabajo.objects.create(gestor=gestor, nombre="Espacio A")
    doc = Documento.objects.create(espacio=espacio, creador=gestor, titulo="Doc 1")
    v1 = guardar_version(doc, gestor, "Hola")
    v2 = guardar_version(doc, gestor, "Hola mundo")
    assert v1.numero_version == 1
    assert v2.numero_version == 2
    assert VersionDocumento.objects.filter(documento=doc).count() == 2
    
@pytest.mark.django_db   
def test_version_es_inmutable():
    gestor = Usuario.objects.create_user(email="a@x.com", username="a", password="Clave12345", nombre="A", tipo_cuenta="GESTOR")
    espacio = EspacioTrabajo.objects.create(gestor=gestor, nombre="Espacio A")
    doc = Documento.objects.create(espacio=espacio, creador=gestor, titulo="Doc 1")
    v1 = guardar_version(doc, gestor, "Hola")

    v1.contenido = "Modificado"
    with pytest.raises(ValueError):
        v1.save()
        
@pytest.mark.django_db
def test_ciclo_completo_lector_puede_ver_pero_no_guardar():
    gestor = Usuario.objects.create_user(email="g@x.com", username="g", password="Clave12345", nombre="G", tipo_cuenta="GESTOR")
    colab = Usuario.objects.create_user(email="c@x.com", username="c", password="Clave12345", nombre="C", tipo_cuenta="COLABORADOR")
    espacio = EspacioTrabajo.objects.create(gestor=gestor, nombre="Espacio A")
    MiembroEspacio.objects.create(espacio=espacio, usuario=gestor)
    doc = Documento.objects.create(espacio=espacio, creador=gestor, titulo="Doc 1")

    cliente = APIClient()

    cliente.force_authenticate(user=gestor)
    r = cliente.post(f"/api/workspaces/{espacio.id}/members/", {"email": "c@x.com"}, format="json")
    assert r.status_code == 201
    r = cliente.post(f"/api/documents/{doc.id}/permissions/", {"email": "c@x.com", "nivel": "LECTURA"}, format="json")
    assert r.status_code == 201

    cliente.force_authenticate(user=colab)
    r = cliente.get(f"/api/documents/{doc.id}/")
    assert r.status_code == 200

    r = cliente.post(f"/api/documents/{doc.id}/save/", {"contenido": "intento"}, format="json")
    assert r.status_code == 403
    
@pytest.mark.django_db
def test_guardar_registra_evento_en_bitacora():
    gestor = Usuario.objects.create_user(email="a@x.com", username="a", password="Clave12345", nombre="A", tipo_cuenta="GESTOR")
    espacio = EspacioTrabajo.objects.create(gestor=gestor, nombre="Espacio A")
    doc = Documento.objects.create(espacio=espacio, creador=gestor, titulo="Doc 1")

    guardar_version(doc, gestor, "Hola")

    eventos = BitacoraAuditoria.objects.filter(recurso_id=doc.id, accion="EDITAR_DOCUMENTO")
    assert eventos.count() == 1
    assert eventos.first().usuario == gestor
    
@pytest.mark.django_db
def test_eliminar_es_borrado_logico():
    gestor = Usuario.objects.create_user(email="a@x.com", username="a", password="Clave12345", nombre="A", tipo_cuenta="GESTOR")
    espacio = EspacioTrabajo.objects.create(gestor=gestor, nombre="Espacio A")
    doc = Documento.objects.create(espacio=espacio, creador=gestor, titulo="Doc 1")
    guardar_version(doc, gestor, "Hola")

    cliente = APIClient()
    cliente.force_authenticate(user=gestor)
    r = cliente.delete(f"/api/documents/{doc.id}/")
    assert r.status_code == 204

    r = cliente.get(f"/api/documents/{doc.id}/")
    assert r.status_code == 404

    doc.refresh_from_db()
    assert doc.eliminado_en is not None
    assert VersionDocumento.objects.filter(documento=doc).count() == 1
    
@pytest.mark.django_db
def test_bitacora_no_muestra_eventos_de_otro_espacio():
    gestor_a = Usuario.objects.create_user(email="a@x.com", username="a", password="Clave12345", nombre="A", tipo_cuenta="GESTOR")
    gestor_b = Usuario.objects.create_user(email="b@x.com", username="b", password="Clave12345", nombre="B", tipo_cuenta="GESTOR")
    espacio_a = EspacioTrabajo.objects.create(gestor=gestor_a, nombre="Espacio A")
    doc_a = Documento.objects.create(espacio=espacio_a, creador=gestor_a, titulo="Secreto de A")
    guardar_version(doc_a, gestor_a, "Contenido secreto")

    cliente = APIClient()
    cliente.force_authenticate(user=gestor_b)
    r = cliente.get("/api/audit/")

    assert r.status_code == 200
    assert r.json() == []