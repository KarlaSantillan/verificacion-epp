from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models


class Rol(models.Model):
    """EPP_M_ROL"""

    ADMINISTRADOR = "Administrador"
    DOCENTE = "Docente/Encargado"

    id_rol = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=30, unique=True)
    descripcion = models.CharField(max_length=150, null=True, blank=True)

    class Meta:
        db_table = "epp_m_rol"
        verbose_name = "rol"
        verbose_name_plural = "roles"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class UsuarioManager(BaseUserManager):
    def create_user(self, correo, password=None, **extra_fields):
        if not correo:
            raise ValueError("El correo es obligatorio.")
        if "rol" not in extra_fields:
            extra_fields["rol"], _ = Rol.objects.get_or_create(nombre=Rol.DOCENTE)
        usuario = self.model(correo=self.normalize_email(correo), **extra_fields)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_superuser(self, correo, password=None, **extra_fields):
        extra_fields["rol"], _ = Rol.objects.get_or_create(nombre=Rol.ADMINISTRADOR)
        return self.create_user(correo, password, **extra_fields)


class Usuario(AbstractBaseUser):
    """EPP_M_USUARIO. Es el usuario del sistema de autenticación de Django."""

    id_usuario = models.AutoField(primary_key=True)
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT, db_column="id_rol", related_name="usuarios")
    nombres = models.CharField(max_length=120)
    apellidos = models.CharField(max_length=120)
    correo = models.EmailField(max_length=120, unique=True)
    # Django guarda aquí el hash de la contraseña (nunca el texto plano).
    password = models.CharField("contraseña", max_length=128, db_column="password_hash")
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    # El último acceso se obtiene de la auditoría (acción LOGIN); no se guarda aquí.
    last_login = None

    objects = UsuarioManager()

    USERNAME_FIELD = "correo"
    EMAIL_FIELD = "correo"
    REQUIRED_FIELDS = ["nombres", "apellidos"]

    class Meta:
        db_table = "epp_m_usuario"
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        ordering = ["apellidos", "nombres"]

    def __str__(self):
        return f"{self.nombres} {self.apellidos}"

    # --- Integración con la autenticación y el panel de administración de Django ---
    @property
    def is_active(self):
        return self.activo

    @property
    def es_administrador(self):
        return self.rol_id is not None and self.rol.nombre == Rol.ADMINISTRADOR

    @property
    def is_staff(self):
        return self.activo and self.es_administrador

    @property
    def is_superuser(self):
        return self.is_staff

    def has_perm(self, perm, obj=None):
        return self.is_staff

    def has_module_perms(self, app_label):
        return self.is_staff
