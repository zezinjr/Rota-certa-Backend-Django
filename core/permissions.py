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


class IsManager(permissions.BasePermission):
    """
    Apenas gestores (Person MANAGER), usuários do painel web.
    É a permissão padrão da API (REST_FRAMEWORK.DEFAULT_PERMISSION_CLASSES);
    endpoints de motorista/colaborador declaram as próprias permissões.
    """

    message = "Apenas gestores podem acessar este recurso."

    def has_permission(self, request, view):
        person = getattr(request.user, "person", None)
        return bool(person and person.type == Person.PersonType.MANAGER)


class IsManagerOrDriver(permissions.BasePermission):
    """Gestor ou motorista (o motorista é limitado às próprias rotas pela view)."""

    message = "Apenas gestores ou motoristas podem acessar este recurso."

    def has_permission(self, request, view):
        person = getattr(request.user, "person", None)
        return bool(
            person
            and person.type in (Person.PersonType.MANAGER, Person.PersonType.DRIVER)
        )
