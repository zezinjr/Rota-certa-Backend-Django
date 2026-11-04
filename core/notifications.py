"""
Avisos da van para os colaboradores, por dois canais:

- WhatsApp (Meta ou Evolution API, ver core/whatsapp.py), para quem ativou os avisos no app
  (whatsapp_opt_in) e tem telefone válido;
- push no app (Firebase Cloud Messaging, ver core/push.py), para quem tem um aparelho
  registrado em /api/me/devices/.

Gatilhos:
- departure: o motorista registrou a saída da rota (evento "departure");
- approaching: a previsão de chegada ao ponto ficou em *_APPROACHING_MINUTES ou menos;
- arriving: a van está a LIVE_ARRIVING_METERS do ponto.

Cada canal tem a sua lista de avisos (WHATSAPP_EVENTS, PUSH_EVENTS). Cada aviso sai no máximo
uma vez por passageiro, canal e dia (ver Notification). O envio roda numa thread depois do
commit, para não atrasar a requisição do GPS do motorista.
"""
import logging
import threading

from django.conf import settings
from django.db import IntegrityError, close_old_connections, transaction
from django.utils import timezone

from . import push, whatsapp
from .live import Phase, live_status
from .models import Notification, PushDevice, RoutePassenger

logger = logging.getLogger(__name__)

Channel = Notification.Channel
Kind = Notification.Kind

TEMPLATE_SETTINGS = {
    Kind.DEPARTURE: "WHATSAPP_TEMPLATE_DEPARTURE",
    Kind.APPROACHING: "WHATSAPP_TEMPLATE_APPROACHING",
    Kind.ARRIVING: "WHATSAPP_TEMPLATE_ARRIVING",
}


# Texto das mensagens na Evolution API e no push: o mesmo dos modelos aprovados na Meta (ver README).
MESSAGE_TEXTS = {
    Kind.DEPARTURE: "Olá, {0}! A van da {1} saiu e já está a caminho. Acompanhe a localização pelo app Rota Certa.",
    Kind.APPROACHING: "Olá, {0}! A van da {1} chega ao seu ponto ({2}) em cerca de {3} minutos.",
    Kind.ARRIVING: "Olá, {0}! A van da {1} está chegando ao seu ponto ({2}). Prepare-se para embarcar.",
}

PUSH_TITLES = {
    Kind.DEPARTURE: "A van saiu",
    Kind.APPROACHING: "A van está a caminho",
    Kind.ARRIVING: "A van está chegando",
}

# canal → (lista de avisos, minutos do "a poucos minutos", integração configurada?)
CHANNEL_SETTINGS = {
    Channel.WHATSAPP: ("WHATSAPP_EVENTS", "WHATSAPP_APPROACHING_MINUTES", whatsapp.is_enabled),
    Channel.PUSH: ("PUSH_EVENTS", "PUSH_APPROACHING_MINUTES", push.is_enabled),
}


def enabled_kinds(channel=Channel.WHATSAPP):
    events_setting, _, is_enabled = CHANNEL_SETTINGS[channel]
    if not is_enabled():
        return set()
    return {k.strip() for k in getattr(settings, events_setting).split(",") if k.strip()} & set(Kind.values)


def approaching_minutes(channel):
    return getattr(settings, CHANNEL_SETTINGS[channel][1])


def _first_name(person):
    return (person.name or "").split(" ")[0] or person.name


def _stop_name(rp):
    stop = rp.route_stop
    return stop.meeting_point.name if stop and stop.meeting_point_id else "seu ponto"


def template_parameters(kind, rp, eta_minutes=None):
    """Valores de {{1}}, {{2}}… de cada modelo, na ordem documentada no README."""
    name, route = _first_name(rp.person), rp.route.name
    if kind == Kind.DEPARTURE:
        return [name, route]
    if kind == Kind.APPROACHING:
        return [name, route, _stop_name(rp), str(eta_minutes or 1)]
    return [name, route, _stop_name(rp)]


def _passengers_to_notify(route, kinds, channel):
    """Passageiros que podem receber `channel` e ainda não receberam todos os `kinds` hoje."""
    today = timezone.localdate()
    rps = (
        RoutePassenger.objects.filter(route=route, is_active=True, person__is_active=True)
        .exclude(boarding_status=RoutePassenger.BoardingStatus.ABSENT)
        .select_related(
            "person", "route", "route__company", "route__vehicle", "route__vehicle__location",
            "route_stop", "route_stop__meeting_point",
        )
    )
    if channel == Channel.WHATSAPP:
        rps = rps.filter(person__whatsapp_opt_in=True)
    else:
        rps = rps.filter(person__push_devices__is_active=True).distinct()
    sent = {}
    for rp_id, kind in Notification.objects.filter(
        route_passenger__route=route, service_date=today, kind__in=kinds, channel=channel,
    ).values_list("route_passenger_id", "kind"):
        sent.setdefault(rp_id, set()).add(kind)
    return [(rp, set(kinds) - sent.get(rp.id, set())) for rp in rps if set(kinds) - sent.get(rp.id, set())]


def _queue(rp, kind, parameters, channel):
    """Registra o aviso (uma vez por dia e canal) e agenda o envio. Retorna a Notification ou None."""
    recipient = ""
    if channel == Channel.WHATSAPP:
        recipient = whatsapp.normalize_phone(rp.person.phone)
        if not recipient:
            logger.info("Passageiro %s sem telefone válido para WhatsApp.", rp.pk)
            return None
    try:
        with transaction.atomic():
            notification = Notification.objects.create(
                route_passenger=rp, kind=kind, channel=channel,
                service_date=timezone.localdate(), recipient=recipient, parameters=parameters,
            )
    except IntegrityError:
        return None  # já registrado hoje (outra requisição chegou antes)
    transaction.on_commit(lambda: _dispatch(notification.pk))
    return notification


def _dispatch(notification_id):
    if settings.WHATSAPP_ASYNC:
        threading.Thread(target=_send_in_thread, args=(notification_id,), daemon=True).start()
    else:
        send_notification(notification_id)


def _send_in_thread(notification_id):
    try:
        send_notification(notification_id)
    finally:
        close_old_connections()


def _send_whatsapp(notification):
    if whatsapp.provider() == whatsapp.PROVIDER_EVOLUTION:
        text = MESSAGE_TEXTS[notification.kind].format(*notification.parameters)
        return whatsapp.send_text(notification.recipient, text)
    template = getattr(settings, TEMPLATE_SETTINGS[notification.kind])
    return whatsapp.send_template(notification.recipient, template, notification.parameters)


def _send_push(notification):
    """Envia para todos os aparelhos ativos do passageiro. Basta um receber para contar como enviado."""
    rp = notification.route_passenger
    devices = list(PushDevice.objects.filter(person_id=rp.person_id, is_active=True))
    if not devices:
        raise push.PushError("nenhum aparelho ativo")
    title = PUSH_TITLES[notification.kind]
    body = MESSAGE_TEXTS[notification.kind].format(*notification.parameters)
    data = {"type": "trip_update", "kind": notification.kind, "trip_id": rp.pk, "route_id": rp.route_id}
    ids, errors = [], []
    for device in devices:
        try:
            ids.append(push.send(device.token, title, body, data))
        except push.InvalidTokenError as exc:
            device.is_active, device.deactivated_reason = False, str(exc)[:255]
            device.save(update_fields=["is_active", "deactivated_reason"])
            errors.append(f"aparelho {device.pk} desativado: {exc}")
        except push.PushError as exc:
            errors.append(f"aparelho {device.pk}: {exc}")
    notification.recipient = str(len(ids))
    if not ids:
        raise push.PushError("; ".join(errors))
    if errors:
        logger.info("Push %s parcial: %s", notification.pk, "; ".join(errors))
    return ",".join(ids)[:255]


def send_notification(notification_id):
    """Envia um aviso pendente (ou que falhou) e grava o resultado."""
    notification = Notification.objects.select_related("route_passenger").get(pk=notification_id)
    if notification.status == Notification.Status.SENT:
        return notification
    sender = _send_push if notification.channel == Channel.PUSH else _send_whatsapp
    try:
        message_id = sender(notification)
    except (whatsapp.WhatsAppError, push.PushError) as exc:
        logger.warning("Aviso %s falhou (%s, %s): %s", notification.pk, notification.channel, notification.kind, exc)
        notification.status, notification.error = Notification.Status.FAILED, str(exc)[:1000]
    else:
        notification.status, notification.error = Notification.Status.SENT, ""
        notification.provider_message_id, notification.sent_at = message_id, timezone.now()
    notification.save(update_fields=["status", "error", "provider_message_id", "sent_at", "recipient"])
    return notification


def notify_route_progress(route):
    """Chamado a cada posição nova da van: dispara "a poucos minutos" e "chegando"."""
    queued = []
    statuses = {}  # live_status de cada passageiro, calculado uma vez para os dois canais
    for channel in Channel.values:
        kinds = enabled_kinds(channel) & {Kind.APPROACHING, Kind.ARRIVING}
        if not kinds:
            continue
        limit = approaching_minutes(channel)
        for rp, missing in _passengers_to_notify(route, kinds, channel):
            if rp.pk not in statuses:
                statuses[rp.pk] = live_status(rp)
            status = statuses[rp.pk]
            if not status["is_live"]:
                continue
            if status["phase"] == Phase.ARRIVING and Kind.ARRIVING in missing:
                queued.append(_queue(rp, Kind.ARRIVING, template_parameters(Kind.ARRIVING, rp), channel))
            elif (
                status["phase"] == Phase.APPROACHING
                and Kind.APPROACHING in missing
                and status["eta"] is not None
                and status["eta"]["minutes"] <= limit
            ):
                params = template_parameters(Kind.APPROACHING, rp, status["eta"]["minutes"])
                queued.append(_queue(rp, Kind.APPROACHING, params, channel))
    return [n for n in queued if n]


def notify_departure(route):
    """Chamado quando o motorista registra a saída da rota."""
    queued = []
    for channel in Channel.values:
        if Kind.DEPARTURE not in enabled_kinds(channel):
            continue
        queued += [
            _queue(rp, Kind.DEPARTURE, template_parameters(Kind.DEPARTURE, rp), channel)
            for rp, _ in _passengers_to_notify(route, {Kind.DEPARTURE}, channel)
        ]
    return [n for n in queued if n]
