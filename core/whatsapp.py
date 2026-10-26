"""
Envio de mensagens pela API oficial do WhatsApp (Meta WhatsApp Cloud API).

Mensagens iniciadas pela empresa precisam usar um modelo (template) aprovado pela Meta,
com os parâmetros {{1}}, {{2}}… preenchidos aqui. Sem WHATSAPP_TOKEN e
WHATSAPP_PHONE_NUMBER_ID no .env, o envio fica desligado.
"""
import json
import re
import urllib.error
import urllib.request

from django.conf import settings


class WhatsAppError(Exception):
    pass


def is_enabled():
    return bool(settings.WHATSAPP_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID)


def normalize_phone(phone):
    """
    Telefone no formato que a API espera: só dígitos, com o código do país.
    Números brasileiros sem o 55 (DDD + número, 10 ou 11 dígitos) ganham o 55.
    Retorna "" se não parecer um telefone válido.
    """
    digits = re.sub(r"\D", "", phone or "")
    if (phone or "").strip().startswith("+"):
        return digits if 8 <= len(digits) <= 15 else ""
    if len(digits) in (10, 11):
        digits = settings.WHATSAPP_DEFAULT_COUNTRY_CODE + digits
    return digits if 12 <= len(digits) <= 15 else ""


def _error_detail(exc):
    body = exc.read().decode("utf-8", "ignore")
    try:
        error = json.loads(body)["error"]
    except (ValueError, KeyError, TypeError):
        return f"HTTP {exc.code}: {body[:300]}"
    details = (error.get("error_data") or {}).get("details")
    text = f"{error.get('code', exc.code)}: {error.get('message', '')}"
    return f"{text} ({details})" if details else text


def send_template(to, template, parameters=(), language=None):
    """Envia o modelo `template` para o telefone `to` e devolve o id da mensagem na Meta."""
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": template,
            "language": {"code": language or settings.WHATSAPP_TEMPLATE_LANGUAGE},
        },
    }
    if parameters:
        payload["template"]["components"] = [
            {"type": "body", "parameters": [{"type": "text", "text": str(p)} for p in parameters]}
        ]
    url = f"{settings.WHATSAPP_API_URL}/{settings.WHATSAPP_API_VERSION}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise WhatsAppError(_error_detail(exc)) from exc
    except (urllib.error.URLError, ValueError) as exc:
        raise WhatsAppError(str(exc)) from exc
    try:
        return data["messages"][0]["id"]
    except (KeyError, IndexError, TypeError):
        raise WhatsAppError(f"Resposta inesperada: {str(data)[:200]}")
