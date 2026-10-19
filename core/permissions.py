from rest_framework import permissions

from .models import Person


class IsDriver(permissions.BasePermission):
    """Apenas usuário cuja Person é DRIVER."""

    message = "Apenas motoristas podem acessar este recurso."

    def has_permission(self, request, view):
        person = getattr(request.user, "person", None)
        return bool(person and person.type == Person.PersonType.DRIVER)


class IsEmployee(permissions.BasePermission):
    """Apenas usuário cuja Person é EMPLOYEE (colaborador/passageiro)."""

    message = "Apenas colaboradores podem acessar este recurso."

    def has_permission(self, request, view):
        person = getattr(request.user, "person", None)
        return bool(person and person.type == Person.PersonType.EMPLOYEE)
