"""Custom DRF permissions."""
from rest_framework.permissions import BasePermission, SAFE_METHODS

from apps.users.models import UserRole


class IsAdminUser(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == UserRole.ADMIN)


class IsAdminOrSupervisor(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role in (UserRole.ADMIN, UserRole.SUPERVISOR)
        )


class IsOperatorOrAbove(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_operator_or_above)


class CanManageDevices(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return bool(request.user and request.user.is_authenticated and request.user.can_manage_devices)


class CanRemoteAccess(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.can_remote_access)


class IsDeviceAuthenticated(BasePermission):
    """
    Custom permission for edge devices.
    Device must pass X-Device-Key header with its auth_key.
    """
    def has_permission(self, request, view):
        return bool(getattr(request, "device", None))
