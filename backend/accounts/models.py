import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser


# Create your models here.
class Usuario(AbstractUser): 
    class TipoCuenta(models.TextChoices): 
        GESTOR = "GESTOR", "Gestor"
        COLABORADOR = "COLABORADOR", "Colaborador"  
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField("correo electrónico", unique=True)
    nombre = models.CharField("nombre", max_length=150)
    tipo_cuenta = models.CharField(max_length=20 ,choices=TipoCuenta.choices)
    
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS =  ["username"]
