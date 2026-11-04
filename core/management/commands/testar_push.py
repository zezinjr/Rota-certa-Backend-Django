from django.core.management.base import BaseCommand, CommandError

from core import push
from core.models import Person, PushDevice


class Command(BaseCommand):
    help = (
        "Manda uma notificação push de teste para os aparelhos de um colaborador "
        "(ou para um token avulso) e mostra o resultado."
    )

    def add_arguments(self, parser):
        target = parser.add_mutually_exclusive_group(required=True)
        target.add_argument("--colaborador-id", type=int, help="id da Person (colaborador) com aparelho registrado")
        target.add_argument("--token", help="token FCM de um aparelho (não precisa estar registrado)")
        parser.add_argument("--titulo", default="Rota Certa")
        parser.add_argument("--mensagem", default="Teste de notificação: se você recebeu, está tudo certo.")

    def handle(self, *args, **opts):
        if not push.is_enabled():
            raise CommandError(
                "Push desligado: configure FCM_SERVICE_ACCOUNT_FILE ou FCM_SERVICE_ACCOUNT_JSON no .env "
                "(conta de serviço do Firebase)."
            )
        try:
            push.access_token()
        except push.PushError as exc:
            raise CommandError(f"Não consegui autenticar no Firebase: {exc}")
        self.stdout.write(f"Projeto do Firebase: {push.project_id()}")

        if opts["token"]:
            tokens = [(None, opts["token"])]
        else:
            person = Person.objects.filter(pk=opts["colaborador_id"]).first()
            if person is None:
                raise CommandError(f"Colaborador {opts['colaborador_id']} não existe.")
            tokens = [(d, d.token) for d in PushDevice.objects.filter(person=person, is_active=True)]
            if not tokens:
                raise CommandError(f"{person.name} não tem aparelho ativo. O app registra em POST /api/me/devices/.")

        ok = 0
        for device, token in tokens:
            label = f"aparelho {device.pk}" if device else "token"
            try:
                message_id = push.send(token, opts["titulo"], opts["mensagem"], {"type": "test"})
            except push.InvalidTokenError as exc:
                if device:
                    device.is_active, device.deactivated_reason = False, str(exc)[:255]
                    device.save(update_fields=["is_active", "deactivated_reason"])
                self.stdout.write(self.style.WARNING(f"{label}: token inválido ({exc}){' — desativado' if device else ''}"))
            except push.PushError as exc:
                self.stdout.write(self.style.ERROR(f"{label}: falhou ({exc})"))
            else:
                ok += 1
                self.stdout.write(self.style.SUCCESS(f"{label}: enviado ({message_id})"))
        if not ok:
            raise CommandError("Nenhuma notificação foi enviada.")
