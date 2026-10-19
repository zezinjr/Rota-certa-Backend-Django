from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import AccessAccount, Company, Person


class Command(BaseCommand):
    help = (
        "Cria um gestor (Person MANAGER) com conta de acesso ao painel web. "
        "Use para criar o primeiro gestor: depois disso, gestores podem ser "
        "cadastrados pelo próprio painel/API."
    )

    def add_arguments(self, parser):
        parser.add_argument("--company-id", type=int, required=True, help="ID da empresa.")
        parser.add_argument("--name", required=True, help="Nome do gestor.")
        parser.add_argument("--code", required=True, help="Matrícula (vira o e-mail: codigo@dominio).")
        parser.add_argument("--phone", required=True, help="Telefone.")
        parser.add_argument("--password", required=True, help="Senha inicial (troca obrigatória no 1º acesso).")

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            company = Company.objects.get(pk=options["company_id"])
        except Company.DoesNotExist as exc:
            raise CommandError(f"Empresa {options['company_id']} não encontrada.") from exc

        person = Person.objects.create(
            company=company,
            name=options["name"],
            phone=options["phone"],
            type=Person.PersonType.MANAGER,
            employee_code=options["code"],
        )
        email = person.get_auto_email()
        # O sinal post_save normalmente já cria a conta; garante caso esteja desligado.
        account, _ = AccessAccount.objects.get_or_create(person=person, defaults={"email": email})
        account.set_password(options["password"])
        account.must_change_password = True
        account.save()

        self.stdout.write(self.style.SUCCESS(f"Gestor criado: {account.email} ({company.name})"))
