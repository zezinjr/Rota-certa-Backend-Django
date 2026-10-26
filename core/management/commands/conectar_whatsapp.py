import base64
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core import whatsapp


class Command(BaseCommand):
    help = (
        "Evolution API: cria a instância (se preciso) e gera o QR code para conectar o número "
        "que vai enviar os avisos. Escaneie em WhatsApp → Aparelhos conectados → Conectar um aparelho."
    )

    def add_arguments(self, parser):
        parser.add_argument("--arquivo", default="whatsapp_qrcode.png", help="Onde salvar o QR code (padrão: whatsapp_qrcode.png).")
        parser.add_argument("--numero", help="Número que vai conectar (ex.: +5592991234567): gera também um código de pareamento.")
        parser.add_argument("--aguardar", type=int, default=120, help="Segundos esperando a leitura do QR code (0 = não espera).")

    def handle(self, *args, **opts):
        if whatsapp.provider() != whatsapp.PROVIDER_EVOLUTION:
            raise CommandError("Este comando é para a Evolution API: use WHATSAPP_PROVIDER=evolution no .env.")
        if not whatsapp.is_enabled():
            raise CommandError("Configure EVOLUTION_API_URL, EVOLUTION_API_KEY e EVOLUTION_INSTANCE no .env.")
        try:
            state = whatsapp.evolution_state()
            if state is None:
                whatsapp.evolution_create_instance()
                self.stdout.write(f"Instância \"{settings.EVOLUTION_INSTANCE}\" criada na Evolution API.")
            else:
                self.stdout.write(f"Estado atual da conexão: {state}.")
            if state == "open":
                self.stdout.write(self.style.SUCCESS("O número já está conectado. Nada a fazer."))
                return
            number = whatsapp.normalize_phone(opts["numero"]) if opts["numero"] else None
            data = whatsapp.evolution_connect(number)
        except whatsapp.WhatsAppError as exc:
            raise CommandError(
                f"Não consegui falar com a Evolution API em {settings.EVOLUTION_API_URL}: {exc}\n"
                "Ela está rodando (docker compose ... up -d) e a EVOLUTION_API_KEY é a mesma do .env?"
            )

        qr = (data or {}).get("base64") or ""
        if qr:
            path = Path(opts["arquivo"]).resolve()
            path.write_bytes(base64.b64decode(qr.split(",", 1)[-1]))
            self.stdout.write(f"QR code salvo em {path}")
            self.stdout.write("Abra o arquivo e escaneie no celular: WhatsApp → Aparelhos conectados → Conectar um aparelho.")
        if (data or {}).get("pairingCode"):
            self.stdout.write(
                f"Ou, no celular, toque em \"Conectar com número de telefone\" e digite o código: {data['pairingCode']}"
            )
        if not qr and not (data or {}).get("pairingCode"):
            raise CommandError(f"A Evolution API não devolveu QR code: {str(data)[:300]}")

        deadline = time.monotonic() + max(0, opts["aguardar"])
        while time.monotonic() < deadline:
            time.sleep(3)
            if whatsapp.evolution_state() == "open":
                self.stdout.write(self.style.SUCCESS("Número conectado! Os avisos já podem ser enviados."))
                return
        if opts["aguardar"]:
            self.stdout.write(self.style.WARNING(
                "Ainda não conectado. O QR code expira em cerca de 1 minuto: rode o comando de novo para gerar outro."
            ))
