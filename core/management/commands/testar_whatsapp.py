from django.core.management.base import BaseCommand, CommandError

from core import whatsapp
from core.models import AccessAccount


class Command(BaseCommand):
    help = (
        "Confere a integração com o WhatsApp enviando uma mensagem de teste. "
        "Na Meta usa um modelo aprovado (padrão: hello_world); na Evolution API envia um texto."
    )

    def add_arguments(self, parser):
        target = parser.add_mutually_exclusive_group(required=True)
        target.add_argument("--telefone", help="Telefone com DDD, ex.: +5592991234567.")
        target.add_argument("--email", help="E-mail de um colaborador: usa o telefone do cadastro dele.")
        parser.add_argument("--mensagem", default="Teste do Rota Certa: os avisos pelo WhatsApp estão funcionando.",
                            help="Evolution API: texto enviado.")
        parser.add_argument("--modelo", default="hello_world", help="Meta: nome do modelo aprovado (padrão: hello_world).")
        parser.add_argument("--idioma", default="en_US", help="Meta: idioma do modelo (padrão: en_US, o do hello_world).")
        parser.add_argument("--parametros", nargs="*", default=[], help="Meta: valores de {{1}}, {{2}}… do modelo, em ordem.")

    def handle(self, *args, **opts):
        evolution = whatsapp.provider() == whatsapp.PROVIDER_EVOLUTION
        if not whatsapp.is_enabled():
            if evolution:
                raise CommandError("Configure EVOLUTION_API_URL, EVOLUTION_API_KEY e EVOLUTION_INSTANCE no .env.")
            raise CommandError("Configure WHATSAPP_TOKEN e WHATSAPP_PHONE_NUMBER_ID no .env (ou use WHATSAPP_PROVIDER=evolution).")
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
            if evolution:
                message_id = whatsapp.send_text(to, opts["mensagem"])
            else:
                message_id = whatsapp.send_template(to, opts["modelo"], opts["parametros"], language=opts["idioma"])
        except whatsapp.WhatsAppError as exc:
            raise CommandError(f"O envio falhou ({whatsapp.provider()}): {exc}")
        self.stdout.write(self.style.SUCCESS(f"Mensagem enviada para {to} (id {message_id})."))
