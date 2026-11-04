"""
Notificações push pelo Firebase Cloud Messaging (API HTTP v1).

Credencial: a conta de serviço do projeto do Firebase (Configurações do projeto → Contas de
serviço → Gerar nova chave privada), em FCM_SERVICE_ACCOUNT_FILE (caminho do JSON) ou
FCM_SERVICE_ACCOUNT_JSON (o JSON em texto ou base64). Com ela o backend assina um JWT (RS256)
e troca por um access token OAuth2 do Google, guardado em memória até perto de expirar.

Sem a conta de serviço, o envio fica desligado.
"""
import base64
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import jwt
from django.conf import settings

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
DEFAULT_TOKEN_URI = "https://oauth2.googleapis.com/token"
FCM_SEND_URL = "https://fcm.googleapis.com/v1/projects/{project}/messages:send"

# Erros do FCM que significam "este token não serve mais": o aparelho é desativado.
INVALID_TOKEN_CODES = {"UNREGISTERED", "INVALID_ARGUMENT", "SENDER_ID_MISMATCH"}


class PushError(Exception):
    pass


class InvalidTokenError(PushError):
    """O FCM recusou o token do aparelho (app desinstalado, token renovado…)."""


_lock = threading.Lock()
_cache = {"account": None, "account_key": None, "token": None, "expires_at": 0.0}


def _load_account():
    raw = (settings.FCM_SERVICE_ACCOUNT_JSON or "").strip()
    path = (settings.FCM_SERVICE_ACCOUNT_FILE or "").strip()
    key = (raw, path)
    if _cache["account_key"] == key:
        return _cache["account"]
    account = None
    try:
        if raw:
            if not raw.startswith("{"):
                raw = base64.b64decode(raw).decode("utf-8")
            account = json.loads(raw)
        elif path:
            with open(path, encoding="utf-8") as fh:
                account = json.load(fh)
    except (OSError, ValueError) as exc:
        raise PushError(f"Conta de serviço do Firebase inválida: {exc}") from exc
    if account is not None and not all(account.get(k) for k in ("client_email", "private_key")):
        raise PushError("Conta de serviço do Firebase sem client_email/private_key.")
    _cache.update(account=account, account_key=key, token=None, expires_at=0.0)
    return account


def is_enabled():
    try:
        return _load_account() is not None and bool(project_id())
    except PushError:
        return False


def project_id():
    account = _load_account() or {}
    return settings.FCM_PROJECT_ID or account.get("project_id", "")


# ---------------------------------------------------------------- HTTP

def _post(url, body, headers, content_type="application/json"):
    data = json.dumps(body).encode() if content_type == "application/json" else urllib.parse.urlencode(body).encode()
    request = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": content_type, **headers})
    try:
        with urllib.request.urlopen(request, timeout=settings.FCM_HTTP_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        raise _http_error(exc) from exc
    except TimeoutError as exc:
        raise PushError(f"sem resposta em {settings.FCM_HTTP_TIMEOUT} s") from exc
    except (OSError, ValueError) as exc:
        raise PushError(str(exc)) from exc


def _http_error(exc):
    body = exc.read().decode("utf-8", "ignore")
    try:
        error = json.loads(body).get("error")
    except (ValueError, AttributeError):
        error = None
    if not isinstance(error, dict):  # erro do OAuth vem como {"error": "invalid_grant", ...}
        return PushError(f"HTTP {exc.code}: {body[:300]}")
    codes = {d.get("errorCode") for d in error.get("details") or [] if isinstance(d, dict)}
    codes.discard(None)
    status = error.get("status", "")
    message = f"{status or exc.code}: {error.get('message', '')}"
    if codes:
        message += f" ({', '.join(sorted(codes))})"
    if codes & INVALID_TOKEN_CODES or (exc.code == 404 and status == "NOT_FOUND"):
        return InvalidTokenError(message)
    return PushError(message)


def access_token():
    """Access token OAuth2 da conta de serviço (renovado 5 min antes de expirar)."""
    with _lock:
        account = _load_account()
        if account is None:
            raise PushError("Push desligado: configure FCM_SERVICE_ACCOUNT_FILE ou FCM_SERVICE_ACCOUNT_JSON.")
        if _cache["token"] and time.time() < _cache["expires_at"] - 300:
            return _cache["token"]
        token_uri = account.get("token_uri") or DEFAULT_TOKEN_URI
        now = int(time.time())
        assertion = jwt.encode(
            {"iss": account["client_email"], "scope": FCM_SCOPE, "aud": token_uri, "iat": now, "exp": now + 3600},
            account["private_key"], algorithm="RS256",
            headers={"kid": account.get("private_key_id")} if account.get("private_key_id") else None,
        )
        data = _post(
            token_uri,
            {"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion},
            {}, content_type="application/x-www-form-urlencoded",
        )
        if not data.get("access_token"):
            raise PushError(f"Resposta inesperada do Google OAuth: {str(data)[:200]}")
        _cache["token"] = data["access_token"]
        _cache["expires_at"] = time.time() + int(data.get("expires_in", 3600))
        return _cache["token"]


def send(token, title, body, data=None):
    """Envia uma notificação para um aparelho e devolve o id da mensagem no FCM."""
    message = {
        "token": token,
        "notification": {"title": title, "body": body},
        # Valores de "data" precisam ser texto.
        "data": {str(k): str(v) for k, v in (data or {}).items()},
        "android": {
            "priority": "HIGH",
            "notification": {"channel_id": settings.FCM_ANDROID_CHANNEL_ID, "sound": "default"},
        },
        "apns": {"payload": {"aps": {"sound": "default"}}},
    }
    url = FCM_SEND_URL.format(project=urllib.parse.quote(project_id(), safe=""))
    result = _post(url, {"message": message}, {"Authorization": f"Bearer {access_token()}"})
    if not result.get("name"):
        raise PushError(f"Resposta inesperada do FCM: {str(result)[:200]}")
    return result["name"]
