from rest_framework import serializers

from .driver_serializers import _route_status_from_events
from .live import company_destination, path_payload
from .models import Address, RoutePassenger, Schedule


def _address_subtitle(addr):
    if not addr:
        return None
    return f"{addr.street}, {addr.number} — {addr.city}/{addr.state}"


def _address_out(addr):
    if not addr:
        return None
    return {
        "id": addr.id,
        "label": _address_subtitle(addr),
        "latitude": addr.latitude,
        "longitude": addr.longitude,
    }


class EmployeeProfileSerializer(serializers.BaseSerializer):
    """Dados do colaborador logado (tela de perfil do app)."""

    def to_representation(self, person):
        account = getattr(person, "access_account", None)
        home = Address.objects.filter(is_active=True, person=person).first()
        return {
            "id": person.id,
            "name": person.name,
            "phone": person.phone,
            "employee_code": person.employee_code,
            "email": account.email if account else None,
            "company_id": person.company_id,
            "company_name": person.company.name,
            "home_address": _address_out(home),
        }


class EmployeeTripSerializer(serializers.BaseSerializer):
    """
    Payload do app do colaborador (RoutePassenger → "minha viagem"):
    rota, veículo/motorista, meu ponto de embarque, paradas, horários e eventos.
    """

    def to_representation(self, rp: RoutePassenger):
        route = rp.route
        vehicle = route.vehicle
        driver = vehicle.driver if vehicle else None

        stops_out = []
        my_stop = None
        for stop in route.stops.all():
            mp = stop.meeting_point
            addr = mp.address
            item = {
                "id": stop.id,
                "sequence": stop.sequence,
                "title": mp.name,
                "subtitle": _address_subtitle(addr),
                "latitude": addr.latitude,
                "longitude": addr.longitude,
                "is_my_stop": stop.id == rp.route_stop_id,
            }
            stops_out.append(item)
            if item["is_my_stop"]:
                my_stop = item

        destination = company_destination(route)
        path = path_payload(route)

        events = list(route.events.all()[:5])
        last_position = None
        if events:
            last_position = {
                "latitude": events[0].latitude,
                "longitude": events[0].longitude,
                "timestamp": events[0].timestamp,
            }
        # GPS da van (app do motorista/simulador), se for mais recente que o último evento.
        location = getattr(vehicle, "location", None) if vehicle else None
        if location is not None and location.route_id in (None, route.id) and (
            last_position is None or location.recorded_at >= last_position["timestamp"]
        ):
            last_position = {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "timestamp": location.recorded_at,
            }

        schedules = Schedule.objects.filter(
            is_active=True, company_id=route.company_id
        ).order_by("time")

        return {
            "id": rp.id,
            "boarding_status": rp.boarding_status,
            "route": {
                "id": route.id,
                "name": route.name,
                "status": _route_status_from_events(route),
            },
            "company": {"id": route.company_id, "name": route.company.name},
            "vehicle": (
                {
                    "id": vehicle.id,
                    "plate_number": vehicle.plate_number,
                    "model": vehicle.model,
                    "capacity": vehicle.capacity,
                }
                if vehicle
                else None
            ),
            "driver": (
                {"id": driver.id, "name": driver.name, "phone": driver.phone}
                if driver
                else None
            ),
            "my_stop": my_stop,
            "stops": stops_out,
            "destination": _address_out(destination),
            "path": path,
            "schedules": [
                {"id": s.id, "time": s.time.strftime("%H:%M"), "weekdays": s.weekdays}
                for s in schedules
            ],
            "last_position": last_position,
            "events": [
                {
                    "id": e.id,
                    "event_type": e.event_type,
                    "description": e.description,
                    "timestamp": e.timestamp,
                }
                for e in events
            ],
        }


class BoardingStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=RoutePassenger.BoardingStatus.choices)
