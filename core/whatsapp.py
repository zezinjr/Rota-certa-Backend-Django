"""
Envio de mensagens pelo WhatsApp, por um de dois provedores (WHATSAPP_PROVIDER no .env):

- "meta": API oficial (Meta WhatsApp Cloud API). Mensagens iniciadas pela empresa precisam
  de um modelo (template) aprovado pela Meta, com os parâmetros {{1}}, {{2}}… preenchidos aqui.
  Precisa de WHATSAPP_TOKEN e WHATSAPP_PHONE_NUMBER_ID.
- "evolution": Evolution API (https://github.com/EvolutionAPI/evolution-api), instalada por
  você, que conecta um número comum de WhatsApp lendo um QR code, como o WhatsApp Web.
  Envia texto livre, sem modelos. Precisa de EVOLUTION_API_URL, EVOLUTION_API_KEY e
  EVOLUTION_INSTANCE. Não é oficial: o WhatsApp pode bloquear o número (ver README).

Sem as credenciais do provedor escolhido, o envio fica desligado.
"""
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

PROVIDER_META = "meta"
PROVIDER_EVOLUTION = "evolution"


class WhatsAppError(Exception):
    pass


def provider():
    return (settings.WHATSAPP_PROVIDER or PROVIDER_META).strip().lower()


def is_enabled():
    if provider() == PROVIDER_EVOLUTION:
        return bool(settings.EVOLUTION_API_URL and settings.EVOLUTION_API_KEY and settings.EVOLUTION_INSTANCE)
    return bool(settings.WHATSAPP_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID)


def normalize_phone(phone):
    """
    Telefone no formato que as APIs esperam: só dígitos, com o código do país.
    Números brasileiros sem o 55 (DDD + número, 10 ou 11 dígitos) ganham o 55.
    Retorna "" se não parecer um telefone válido.
    """
    digits = re.sub(r"\D", "", phone or "")
    if (phone or "").strip().startswith("+"):
        return digits if 8 <= len(digits) <= 15 else ""
    if len(digits) in (10, 11):
        digits = settings.WHATSAPP_DEFAULT_COUNTRY_CODE + digits
    return digits if 12 <= len(digits) <= 15 else ""


# ---------------------------------------------------------------- HTTP

def _error_detail(exc):
    body = exc.read().decode("utf-8", "ignore")
    try:
        data = json.loads(body)
    except ValueError:
        return f"HTTP {exc.code}: {body[:300]}"
    error = data.get("error") if isinstance(data, dict) else None
    if isinstance(error, dict):  # formato da Meta
        details = (error.get("error_data") or {}).get("details")
        text = f"{error.get('code', exc.code)}: {error.get('message', '')}"
        return f"{text} ({details})" if details else text
    response = data.get("response") if isinstance(data, dict) else None
    if isinstance(response, dict) and response.get("message"):  # formato da Evolution
        return f"HTTP {exc.code}: {json.dumps(response['message'], ensure_ascii=False)[:300]}"
    return f"HTTP {exc.code}: {body[:300]}"


def _request(method, url, headers, payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json", **headers}, method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.WHATSAPP_HTTP_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        raise WhatsAppError(_error_detail(exc)) from exc
    except TimeoutError as exc:
        raise WhatsAppError(f"sem resposta em {settings.WHATSAPP_HTTP_TIMEOUT} s") from exc
    except (OSError, ValueError) as exc:  # URLError, conexão recusada, JSON inválido
        raise WhatsAppError(str(exc)) from exc


# ---------------------------------------------------------------- Meta (oficial)

def send_template(to, template, parameters=(), language=None):
    """Meta: envia o modelo aprovado `template` e devolve o id da mensagem."""
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
    data = _request("POST", url, {"Authorization": f"Bearer {settings.WHATSAPP_TOKEN}"}, payload)
    try:
        return data["messages"][0]["id"]
    except (KeyError, IndexError, TypeError):
        raise WhatsAppError(f"Resposta inesperada: {str(data)[:200]}")


# ---------------------------------------------------------------- Evolution API

def _evolution(method, path, payload=None):
    base = settings.EVOLUTION_API_URL.rstrip("/")
    return _request(method, f"{base}/{path}", {"apikey": settings.EVOLUTION_API_KEY}, payload)


def _instance():
    return urllib.parse.quote(settings.EVOLUTION_INSTANCE, safe="")


def send_text(to, text):
    """Evolution: envia texto livre e devolve o id da mensagem."""
    data = _evolution("POST", f"message/sendText/{_instance()}", {"number": to, "text": text})
    message_id = (data.get("key") or {}).get("id") if isinstance(data, dict) else None
    if not message_id:
        raise WhatsAppError(f"Resposta inesperada: {str(data)[:200]}")
    return message_id


def evolution_state():
    """Estado da conexão do número: "open" (conectado), "connecting", "close" ou None se a instância não existe."""
    try:
        data = _evolution("GET", f"instance/connectionState/{_instance()}")
    except WhatsAppError as exc:
        if "404" in str(exc) or "does not exist" in str(exc):
            return None
        raise
    return (data.get("instance") or {}).get("state")


def evolution_create_instance():
    return _evolution("POST", "instance/create", {
        "instanceName": settings.EVOLUTION_INSTANCE,
        "integration": "WHATSAPP-BAILEYS",
        "qrcode": True,
    })


def evolution_connect(number=None):
    """Pede um QR code (e, com `number`, um código de pareamento) para conectar o número."""
    query = f"?number={number}" if number else ""
    return _evolution("GET", f"instance/connect/{_instance()}{query}")
