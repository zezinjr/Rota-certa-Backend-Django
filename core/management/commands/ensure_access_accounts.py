from django.core.management.base import BaseCommand
from django.db import transaction

from core.access_passwords import generate_initial_access_password
from core.models import AccessAccount, Person


class Command(BaseCommand):
    help = (
        "Cria AccessAccount com e-mail automático para pessoas ativas sem conta. "
        "Novas pessoas passam a receber conta no save (sinal); use este comando para "
        "registros antigos ou após desligar ACCESS_ACCOUNT_AUTO_CREATE."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=None,
            help=(
                "Senha inicial fixa. Se omitida, usa DDMMAAAA de created_at + "
                "últimos 4 dígitos do telefone."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas lista o que seria criado, sem gravar.",
        )

    def handle(self, *args, **options):
        fixed_password = options["password"]
        dry = options["dry_run"]
        qs = (
            Person.objects.filter(is_active=True)
            .select_related("company")
            .order_by("id")
        )
        created = 0
        for person in qs:
            if AccessAccount.objects.filter(person=person).exists():
                continue
            email = person.get_auto_email()
            if not email:
                self.stdout.write(
                    self.style.WARNING(
                        f"Pessoa id={person.pk} ignorada: sem employee_code/license_number."
                    )
                )
                continue
            if AccessAccount.objects.filter(email=email).exists():
                self.stdout.write(
                    self.style.ERROR(
                        f"E-mail {email} já existe para outra conta; pessoa id={person.pk}."
                    )
                )
                continue
            self.stdout.write(f"Criar conta: {email} (pessoa id={person.pk})")
            if dry:
                created += 1
                continue
            with transaction.atomic():
                acc = AccessAccount(
                    person=person,
                    email=email,
                    must_change_password=True,
                )
                password = fixed_password or generate_initial_access_password(person)
                acc.set_password(password)
                acc.save()
            created += 1
        if dry:
            self.stdout.write(self.style.NOTICE(f"Simulação: {created} conta(s)."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Pronto: {created} conta(s) criada(s)."))
