"""
User models — custom User with two roles: admin and operator.

Admin:
  - Full access, manages devices and operator accounts
Operator:
  - Read/monitor access, filtered by assigned oil fields (месторождения)
  - Cannot add/edit/delete devices or manage accounts
"""
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserRole(models.TextChoices):
    ADMIN    = "admin",    _("Администратор")
    OPERATOR = "operator", _("Оператор")


class User(AbstractUser):
    """Extended user with role-based access control."""

    email = models.EmailField(_("email address"), unique=True, blank=True, default="")
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.OPERATOR,
        db_index=True,
    )
    # Unique employee identifier, auto-generated on creation (e.g. OP-0001)
    employee_number = models.CharField(
        max_length=20, unique=True, blank=True,
        verbose_name=_("Табельный номер"),
    )
    is_frozen = models.BooleanField(
        default=False,
        verbose_name=_("Аккаунт заморожен"),
        help_text=_("Замороженный оператор не может войти в систему."),
    )
    phone = models.CharField(max_length=30, blank=True)
    last_activity = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        db_table = "users_user"
        verbose_name = _("Пользователь")
        verbose_name_plural = _("Пользователи")
        indexes = [
            models.Index(fields=["role"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    @property
    def is_admin(self):
        return self.role == UserRole.ADMIN

    @property
    def full_name(self):
        return self.get_full_name() or self.username

    def get_allowed_field_ids(self):
        """
        Returns set of Field IDs this user may access.
        Returns None for admin (all fields allowed).
        Returns empty set if operator has no assigned fields.
        """
        if self.is_admin:
            return None
        try:
            return set(self.profile.assigned_fields.values_list("id", flat=True))
        except OperatorProfile.DoesNotExist:
            return set()


class OperatorProfile(models.Model):
    """Extended profile for operators — field assignment and notification preferences."""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="profile"
    )
    # Fields (месторождения) this operator can access
    assigned_fields = models.ManyToManyField(
        "devices.Field",
        blank=True,
        related_name="assigned_operators",
        verbose_name=_("Назначенные месторождения"),
    )
    # Notification settings
    notify_critical = models.BooleanField(default=True)
    notify_offline  = models.BooleanField(default=True)
    notify_warning  = models.BooleanField(default=False)
    notify_email    = models.BooleanField(default=False)
    # Meta
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users_operator_profile"
        verbose_name = _("Профиль оператора")
        verbose_name_plural = _("Профили операторов")

    def __str__(self):
        return f"Profile({self.user.username})"
