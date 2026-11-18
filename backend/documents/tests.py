import pytest
from workspaces.models import EspacioTrabajo, MiembroEspacio
from documents.models import VersionDocumento, Documento, PermisoDocumento
from documents.services import obtener_nivel, tiene_nivel, guardar_version
from django.contrib.auth import get_user_model

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