"""
Avisos da van para os colaboradores pelo WhatsApp (Meta ou Evolution API, ver core/whatsapp.py).

Gatilhos:
- departure: o motorista registrou a saída da rota (evento "departure");
- approaching: a previsão de chegada ao ponto ficou em WHATSAPP_APPROACHING_MINUTES ou menos;
- arriving: a van está a LIVE_ARRIVING_METERS do ponto.

Cada aviso sai no máximo uma vez por passageiro por dia (ver Notification) e só para quem
ativou os avisos no app. O envio roda numa thread depois do commit, para não atrasar a
requisição do GPS do motorista.
"""
import logging
import threading

from django.conf import settings
from django.db import IntegrityError, close_old_connections, transaction
from django.utils import timezone

from . import whatsapp
from .live import Phase, live_status
from .models import Notification, RoutePassenger

logger = logging.getLogger(__name__)

TEMPLATE_SETTINGS = {
    Notification.Kind.DEPARTURE: "WHATSAPP_TEMPLATE_DEPARTURE",
    Notification.Kind.APPROACHING: "WHATSAPP_TEMPLATE_APPROACHING",
    Notification.Kind.ARRIVING: "WHATSAPP_TEMPLATE_ARRIVING",
}


# Texto das mensagens na Evolution API: o mesmo dos modelos aprovados na Meta (ver README).
MESSAGE_TEXTS = {
    Notification.Kind.DEPARTURE: "Olá, {0}! A van da {1} saiu e já está a caminho. Acompanhe a localização pelo app Rota Certa.",
    Notification.Kind.APPROACHING: "Olá, {0}! A van da {1} chega ao seu ponto ({2}) em cerca de {3} minutos.",
    Notification.Kind.ARRIVING: "Olá, {0}! A van da {1} está chegando ao seu ponto ({2}). Prepare-se para embarcar.",
}


def enabled_kinds():
    if not whatsapp.is_enabled():
        return set()
    return {k.strip() for k in settings.WHATSAPP_EVENTS.split(",") if k.strip()} & set(Notification.Kind.values)


def _first_name(person):
    return (person.name or "").split(" ")[0] or person.name


def _stop_name(rp):
    stop = rp.route_stop
    return stop.meeting_point.name if stop and stop.meeting_point_id else "seu ponto"


def template_parameters(kind, rp, eta_minutes=None):
    """Valores de {{1}}, {{2}}… de cada modelo, na ordem documentada no README."""
    name, route = _first_name(rp.person), rp.route.name
    if kind == Notification.Kind.DEPARTURE:
        return [name, route]
    if kind == Notification.Kind.APPROACHING:
        return [name, route, _stop_name(rp), str(eta_minutes or 1)]
    return [name, route, _stop_name(rp)]


def _passengers_to_notify(route, kinds):
    """Passageiros que aceitaram os avisos e ainda não receberam todos os `kinds` hoje."""
    today = timezone.localdate()
    rps = (
        RoutePassenger.objects.filter(
            route=route, is_active=True, person__is_active=True, person__whatsapp_opt_in=True,
        )
        .exclude(boarding_status=RoutePassenger.BoardingStatus.ABSENT)
        .select_related(
            "person", "route", "route__company", "route__vehicle", "route__vehicle__location",
            "route_stop", "route_stop__meeting_point",
        )
    )
    sent = {}
    for rp_id, kind in Notification.objects.filter(
        route_passenger__route=route, service_date=today, kind__in=kinds,
    ).values_list("route_passenger_id", "kind"):
        sent.setdefault(rp_id, set()).add(kind)
    return [(rp, set(kinds) - sent.get(rp.id, set())) for rp in rps if set(kinds) - sent.get(rp.id, set())]


def _queue(rp, kind, parameters):
    """Registra o aviso (uma vez por dia) e agenda o envio. Retorna a Notification ou None."""
    recipient = whatsapp.normalize_phone(rp.person.phone)
    if not recipient:
        logger.info("Passageiro %s sem telefone válido para WhatsApp.", rp.pk)
        return None
    try:
        with transaction.atomic():
            notification = Notification.objects.create(
                route_passenger=rp, kind=kind, channel=Notification.Channel.WHATSAPP,
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


def send_notification(notification_id):
    """Envia um aviso pendente (ou que falhou) e grava o resultado."""
    notification = Notification.objects.select_related("route_passenger").get(pk=notification_id)
    if notification.status == Notification.Status.SENT:
        return notification
    try:
        if whatsapp.provider() == whatsapp.PROVIDER_EVOLUTION:
            text = MESSAGE_TEXTS[notification.kind].format(*notification.parameters)
            message_id = whatsapp.send_text(notification.recipient, text)
        else:
            template = getattr(settings, TEMPLATE_SETTINGS[notification.kind])
            message_id = whatsapp.send_template(notification.recipient, template, notification.parameters)
    except whatsapp.WhatsAppError as exc:
        logger.warning("WhatsApp falhou (aviso %s, %s): %s", notification.pk, notification.kind, exc)
        notification.status, notification.error = Notification.Status.FAILED, str(exc)[:1000]
    else:
        notification.status, notification.error = Notification.Status.SENT, ""
        notification.provider_message_id, notification.sent_at = message_id, timezone.now()
    notification.save(update_fields=["status", "error", "provider_message_id", "sent_at"])
    return notification


def notify_route_progress(route):
    """Chamado a cada posição nova da van: dispara "a poucos minutos" e "chegando"."""
    kinds = enabled_kinds() & {Notification.Kind.APPROACHING, Notification.Kind.ARRIVING}
    if not kinds:
        return []
    queued = []
    limit = settings.WHATSAPP_APPROACHING_MINUTES
    for rp, missing in _passengers_to_notify(route, kinds):
        status = live_status(rp)
        if not status["is_live"]:
            continue
        if status["phase"] == Phase.ARRIVING and Notification.Kind.ARRIVING in missing:
            queued.append(_queue(rp, Notification.Kind.ARRIVING, template_parameters(Notification.Kind.ARRIVING, rp)))
        elif (
            status["phase"] == Phase.APPROACHING
            and Notification.Kind.APPROACHING in missing
            and status["eta"] is not None
            and status["eta"]["minutes"] <= limit
        ):
            params = template_parameters(Notification.Kind.APPROACHING, rp, status["eta"]["minutes"])
            queued.append(_queue(rp, Notification.Kind.APPROACHING, params))
    return [n for n in queued if n]


def notify_departure(route):
    """Chamado quando o motorista registra a saída da rota."""
    if Notification.Kind.DEPARTURE not in enabled_kinds():
        return []
    queued = [
        _queue(rp, Notification.Kind.DEPARTURE, template_parameters(Notification.Kind.DEPARTURE, rp))
        for rp, _ in _passengers_to_notify(route, {Notification.Kind.DEPARTURE})
    ]
    return [n for n in queued if n]
