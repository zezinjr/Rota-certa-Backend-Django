from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers


def _route_status_from_events(route):
    """Heurística simples para UI (Em rota / Aguardando / Atrasado)."""
    ev = route.events.order_by("-timestamp").first()
    if not ev:
        return "waiting"
    if ev.event_type in ("delay", "incident"):
        return "delayed"
    if ev.event_type == "departure":
        return "in_route"
    return "waiting"


class DriverRouteBoardSerializer(serializers.BaseSerializer):
    """
    Payload alinhado ao app motorista: paradas ordenadas (timeline / RouteStopCard)
    e passageiros (PassengerCard: name, point, status).
    """

    def to_representation(self, route):
        stops_out = []
        for stop in (
            route.stops.select_related("meeting_point", "meeting_point__address")
            .filter(is_active=True)
            .order_by("sequence")
        ):
            mp = stop.meeting_point
            addr = mp.address
            subtitle = f"{addr.street}, {addr.number} — {addr.city}/{addr.state}"
            stops_out.append(
                {
                    "id": stop.id,
                    "sequence": stop.sequence,
                    "title": mp.name,
                    "subtitle": subtitle,
                    "latitude": addr.latitude,
                    "longitude": addr.longitude,
                    "passenger_count": stop.passengers.filter(is_active=True).count(),
                }
            )

        passengers_out = []
        for rp in route.route_passengers.select_related(
            "person", "route_stop", "route_stop__meeting_point"
        ).filter(is_active=True):
            if rp.route_stop_id:
                point = rp.route_stop.meeting_point.name
            else:
                point = route.name
            passengers_out.append(
                {
                    "id": rp.id,
                    "person_id": rp.person_id,
                    "name": rp.person.name,
                    "point": point,
                    "status": rp.boarding_status,
                    "route_stop_id": rp.route_stop_id,
                }
            )

        vehicle = route.vehicle
        return {
            "id": route.id,
            "name": route.name,
            "company_id": route.company_id,
            "company_name": route.company.name,
            "vehicle": (
                {
                    "id": vehicle.id,
                    "plate_number": vehicle.plate_number,
                    "model": vehicle.model,
                }
                if vehicle
                else None
            ),
            "route_status": _route_status_from_events(route),
            "eta_next_stop": None,
            "stops": stops_out,
            "passengers": passengers_out,
        }


class VehicleLocationInputSerializer(serializers.Serializer):
    """GPS enviado pelo app do motorista."""

    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, min_value=-90, max_value=90)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, min_value=-180, max_value=180)
    heading = serializers.FloatField(required=False, allow_null=True, min_value=0, max_value=360)
    speed = serializers.FloatField(required=False, allow_null=True, min_value=0)
    recorded_at = serializers.DateTimeField(required=False)

    def validate_recorded_at(self, value):
        # Relógio do celular adiantado não pode deixar a posição "do futuro".
        if value > timezone.now() + timedelta(minutes=1):
            return timezone.now()
        return value
