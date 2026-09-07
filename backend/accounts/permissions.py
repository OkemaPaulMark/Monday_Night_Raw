from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdminRole(BasePermission):
    """Only ADMIN role (or Django superuser) may mutate admin resources."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and getattr(user, 'is_app_admin', False)
        )


class IsAdminOrReadOnly(BasePermission):
    """Authenticated users can read; only admins can write."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return getattr(user, 'is_app_admin', False)
