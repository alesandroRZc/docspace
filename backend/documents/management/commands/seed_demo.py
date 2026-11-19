from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from documents.models import Documento, PermisoDocumento
from documents.services import guardar_version
from workspaces.models import EspacioTrabajo, MiembroEspacio

Usuario = get_user_model()
CLAVE_DEMO = "Demo12345"


def crear_usuario(email, username, nombre, tipo):
    usuario, creado = Usuario.objects.get_or_create(
        email=email,
        defaults={"username": username, "nombre": nombre, "tipo_cuenta": tipo},
    )
    if creado:
        usuario.set_password(CLAVE_DEMO)
        usuario.save()
    return usuario


class Command(BaseCommand):
    help = "Crea usuarios, un espacio y un documento de demostración."

    @transaction.atomic
    def handle(self, *args, **options):
        gestor = crear_usuario("gestor@demo.com", "gestor_demo", "Gestor Demo", "GESTOR")
        lector = crear_usuario("lector@demo.com", "lector_demo", "Lector Demo", "COLABORADOR")
        editor = crear_usuario("editor@demo.com", "editor_demo", "Editor Demo", "COLABORADOR")
        crear_usuario("intruso@demo.com", "intruso_demo", "Usuario Sin Espacio", "COLABORADOR")

        espacio, _ = EspacioTrabajo.objects.get_or_create(gestor=gestor, nombre="Espacio Demo")
        for usuario in [gestor, lector, editor]:
            MiembroEspacio.objects.get_or_create(espacio=espacio, usuario=usuario)

        documento = Documento.objects.filter(
            espacio=espacio,
            titulo="Manual de bienvenida",
            eliminado_en__isnull=True,
        ).first()
        if documento is None:
            documento = Documento.objects.create(espacio=espacio, titulo="Manual de bienvenida", creador=gestor)
            guardar_version(documento, gestor, "Bienvenido a DocSpace.")
            guardar_version(documento, gestor, "Bienvenido a DocSpace.\nEste documento tiene historial de versiones.")
            
        PermisoDocumento.objects.get_or_create(documento=documento, usuario=lector, defaults={"nivel": "LECTURA"})
        PermisoDocumento.objects.get_or_create(documento=documento, usuario=editor, defaults={"nivel": "EDICION"})

        self.stdout.write(self.style.SUCCESS(f"Datos de demostración listos. Contraseña de todos: {CLAVE_DEMO}"))