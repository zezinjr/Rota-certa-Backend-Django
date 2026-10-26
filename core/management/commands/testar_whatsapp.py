from django.core.management.base import BaseCommand, CommandError

from core import whatsapp
from core.models import AccessAccount


class Command(BaseCommand):
    help = (
        "Confere a integração com o WhatsApp enviando uma mensagem de teste. "
        "Por padrão usa o modelo hello_world, que já vem aprovado em toda conta da Meta."
    )

    def add_arguments(self, parser):
        target = parser.add_mutually_exclusive_group(required=True)
        target.add_argument("--telefone", help="Telefone com DDD, ex.: +5592991234567.")
        target.add_argument("--email", help="E-mail de um colaborador: usa o telefone do cadastro dele.")
        parser.add_argument("--modelo", default="hello_world", help="Nome do modelo aprovado (padrão: hello_world).")
        parser.add_argument("--idioma", default="en_US", help="Idioma do modelo (padrão: en_US, o do hello_world).")
        parser.add_argument("--parametros", nargs="*", default=[], help="Valores de {{1}}, {{2}}… do modelo, em ordem.")

    def handle(self, *args, **opts):
        if not whatsapp.is_enabled():
            raise CommandError("Configure WHATSAPP_TOKEN e WHATSAPP_PHONE_NUMBER_ID no .env.")
        phone = opts["telefone"]
        if opts["email"]:
            account = AccessAccount.objects.filter(email=opts["email"].strip().lower()).select_related("person").first()
            if account is None:
                raise CommandError(f"Conta {opts['email']} não encontrada.")
            phone = account.person.phone
        to = whatsapp.normalize_phone(phone)
        if not to:
            raise CommandError(f"Telefone inválido: {phone!r}.")
        try:
            message_id = whatsapp.send_template(to, opts["modelo"], opts["parametros"], language=opts["idioma"])
        except whatsapp.WhatsAppError as exc:
            raise CommandError(f"A Meta recusou o envio: {exc}")
        self.stdout.write(self.style.SUCCESS(f"Mensagem enviada para {to} (id {message_id})."))
