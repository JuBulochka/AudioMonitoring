"""Custom DRF permissions."""
from rest_framework.permissions import BasePermission, SAFE_METHODS

from apps.users.models import UserRole


class IsAdminUser(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == UserRole.ADMIN)


class IsAdminOrSupervisor(BasePermission):
    """Now equivalent to IsAdminUser — only admins have elevated permissions."""
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role == UserRole.ADMIN
        )


class IsOperatorOrAbove(BasePermission):
    """Any authenticated user (admin or operator)."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class CanManageDevices(BasePermission):
    """Only admins can mutate devices; operators can read."""
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return bool(request.user and request.user.is_authenticated and request.user.is_admin)


class CanRemoteAccess(BasePermission):
    """Any authenticated user can use remote access."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class IsDeviceAuthenticated(BasePermission):
    """
    Custom permission for edge devices.
    Device must pass X-Device-Key header with its auth_key.
    """
    def has_permission(self, request, view):
        return bool(getattr(request, "device", None))
