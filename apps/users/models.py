"""
User models — custom User with roles and operator profiles.

Design decisions:
- Single User model extending AbstractUser (avoids profile divergence issues).
- Role stored directly on User for fast permission checks without extra joins.
- OperatorProfile stores operational preferences and regional assignment.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserRole(models.TextChoices):
    ADMIN = "admin", _("Администратор")
    SUPERVISOR = "supervisor", _("Супервайзер")
    OPERATOR = "operator", _("Оператор")
    ENGINEER = "engineer", _("Инженер")
    READONLY = "readonly", _("Только просмотр")


class User(AbstractUser):
    """Extended user with role-based access control."""

    email = models.EmailField(_("email address"), unique=True)
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.OPERATOR,
        db_index=True,
    )
    phone = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
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
    def is_operator_or_above(self):
        return self.role in (UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.OPERATOR)

    @property
    def can_manage_devices(self):
        return self.role in (UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.ENGINEER)

    @property
    def can_remote_access(self):
        return self.role in (UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.ENGINEER)


class OperatorProfile(models.Model):
    """Extended profile for operators — regional assignment and notification preferences."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    # Regional assignment — operator sees only their assigned regions
    assigned_regions = models.ManyToManyField(
        "devices.Region",
        blank=True,
        related_name="assigned_operators",
        verbose_name=_("Назначенные регионы"),
    )
    # Notification settings
    notify_critical = models.BooleanField(default=True)
    notify_offline = models.BooleanField(default=True)
    notify_warning = models.BooleanField(default=False)
    notify_email = models.BooleanField(default=False)
    # Display preferences
    preferred_timezone = models.CharField(max_length=64, default="UTC")
    items_per_page = models.PositiveSmallIntegerField(default=50)
    # Meta
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users_operator_profile"
        verbose_name = _("Профиль оператора")
        verbose_name_plural = _("Профили операторов")

    def __str__(self):
        return f"Profile({self.user.username})"
