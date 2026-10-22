"""
Acompanhamento ao vivo da van para o app do colaborador.

O trajeto considerado é a sequência das paradas da rota até a empresa (linha reta
entre os pontos). A posição da van é projetada nesse trajeto para saber quanto
falta até a parada do colaborador. A previsão usa velocidade média + tempo de
parada, sem chamar APIs pagas (a previsão com trânsito fica para a etapa 2).
"""
import math
from dataclasses import dataclass

from django.conf import settings
from django.utils import timezone

from .models import Address

EARTH_RADIUS_M = 6_371_000
# Distância (m) a partir da qual uma parada conta como "já passou" pela van.
REACHED_TOLERANCE_M = 30


def _setting(name, default):
    return getattr(settings, name, default)


def haversine_m(a, b) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def bearing_deg(a, b) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    y = math.sin(lon2 - lon1) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def company_destination(route):
    """Endereço da empresa (endereço da empresa que não é ponto de encontro)."""
    return (
        Address.objects.filter(is_active=True, person__isnull=True, company=route.company)
        .exclude(meeting_points__isnull=False)
        .first()
    )


@dataclass
class PathPoint:
    lat: float
    lng: float
    stop: object = None  # RouteStop, ou None para a empresa


def route_path(route, stops=None):
    """Paradas em ordem + empresa no final."""
    stops = list(stops if stops is not None else route.stops.filter(is_active=True).select_related(
        "meeting_point__address").order_by("sequence"))
    path = [
        PathPoint(float(s.meeting_point.address.latitude), float(s.meeting_point.address.longitude), s)
        for s in stops
    ]
    dest = company_destination(route)
    if dest is not None:
        path.append(PathPoint(float(dest.latitude), float(dest.longitude), None))
    return path


def cumulative_distances(path):
    cum = [0.0]
    for a, b in zip(path, path[1:]):
        cum.append(cum[-1] + haversine_m((a.lat, a.lng), (b.lat, b.lng)))
    return cum


def _segment_candidates(point, path, cum):
    """Projeção de `point` em cada segmento: (segmento, fração, distância percorrida, afastamento)."""
    lat0 = math.radians(point[0])
    kx = math.cos(lat0) * math.pi / 180 * EARTH_RADIUS_M
    ky = math.pi / 180 * EARTH_RADIUS_M
    px, py = point[1] * kx, point[0] * ky
    out = []
    for i, (a, b) in enumerate(zip(path, path[1:])):
        ax, ay, bx, by = a.lng * kx, a.lat * ky, b.lng * kx, b.lat * ky
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        t = 0.0 if seg2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg2))
        off = math.hypot(px - (ax + t * dx), py - (ay + t * dy))
        out.append((i, t, cum[i] + t * (cum[i + 1] - cum[i]), off))
    return out


def locate_on_path(point, path, cum, previous_along=None):
    """
    Distância percorrida (m) da van no trajeto. Entre os trechos próximos do ponto,
    prefere o que continua a partir da posição anterior (`previous_along`), para
    não "pular" de trecho quando o trajeto se cruza.
    """
    if len(path) < 2:
        return 0.0
    candidates = _segment_candidates(point, path, cum)
    min_off = min(c[3] for c in candidates)
    near = [c for c in candidates if c[3] <= min_off + 40]
    if previous_along is None:
        return min(near, key=lambda c: c[3])[2]
    ahead = [c for c in near if c[2] >= previous_along - 50] or near
    return min(ahead, key=lambda c: abs(c[2] - previous_along))[2]


def progress_from_along(along, cum):
    """Converte distância percorrida em (segmento, fração) para o app desenhar o trecho já feito."""
    if len(cum) < 2:
        return 0, 0.0
    along = max(0.0, min(along, cum[-1]))
    for i in range(len(cum) - 1):
        if along <= cum[i + 1] or i == len(cum) - 2:
            length = cum[i + 1] - cum[i]
            return i, (0.0 if length == 0 else (along - cum[i]) / length)
    return len(cum) - 2, 1.0


def save_vehicle_location(vehicle, route, latitude, longitude, heading=None, speed=None, recorded_at=None):
    """Grava a última posição do veículo calculando o progresso no trajeto da rota."""
    from .models import VehicleLocation

    previous = VehicleLocation.objects.filter(vehicle=vehicle).first()
    previous_along = (
        previous.progress_meters
        if previous is not None and previous.route_id == route.id
        and previous.progress_meters is not None
        else None
    )
    path = route_path(route)
    along = None
    if len(path) >= 2:
        along = locate_on_path((float(latitude), float(longitude)), path, cumulative_distances(path), previous_along)
    location, _ = VehicleLocation.objects.update_or_create(
        vehicle=vehicle,
        defaults={
            "route": route,
            "latitude": round(float(latitude), 6),
            "longitude": round(float(longitude), 6),
            "heading": heading,
            "speed": speed,
            "progress_meters": along,
            "recorded_at": recorded_at or timezone.now(),
        },
    )
    return location


class Phase:
    WAITING = "waiting"              # sem posição ao vivo (van parada ou sem GPS)
    APPROACHING = "approaching"      # a caminho do ponto do colaborador
    ARRIVING = "arriving"            # chegando / no ponto
    PASSED = "passed"                # já passou do ponto (a caminho da empresa)
    AT_DESTINATION = "at_destination"


def live_status(rp, now=None):
    """Situação ao vivo da viagem de um passageiro (RoutePassenger)."""
    now = now or timezone.now()
    route = rp.route
    vehicle = route.vehicle
    location = getattr(vehicle, "location", None) if vehicle else None
    max_age = _setting("LIVE_LOCATION_MAX_AGE_SECONDS", 120)

    result = {
        "trip_id": rp.id,
        "is_live": False,
        "phase": Phase.WAITING,
        "vehicle": None,
        "eta": None,
        "next_stop_sequence": None,
        "path_progress": None,
        "updated_at": now,
    }
    if location is None or (location.route_id and location.route_id != route.id):
        return result

    age = max(0, int((now - location.recorded_at).total_seconds()))
    result["vehicle"] = {
        "latitude": float(location.latitude),
        "longitude": float(location.longitude),
        "heading": location.heading,
        "speed": location.speed,
        "recorded_at": location.recorded_at,
        "age_seconds": age,
    }
    if age > max_age:
        return result  # posição antiga: mostra no mapa, mas não é "ao vivo"

    result["is_live"] = True
    path = route_path(route)
    if not path:
        result["phase"] = Phase.APPROACHING
        return result

    cum = cumulative_distances(path)
    along = location.progress_meters
    if along is None:
        along = locate_on_path((float(location.latitude), float(location.longitude)), path, cum)
    segment, fraction = progress_from_along(along, cum)
    result["path_progress"] = {"segment": segment, "fraction": round(fraction, 4)}

    pending = [j for j, p in enumerate(path) if p.stop is not None and cum[j] > along + REACHED_TOLERANCE_M]
    result["next_stop_sequence"] = path[pending[0]].stop.sequence if pending else None

    arriving_m = _setting("LIVE_ARRIVING_METERS", 300)
    total = cum[-1]
    if path[-1].stop is None and total - along <= _setting("LIVE_DESTINATION_METERS", 150):
        result["phase"] = Phase.AT_DESTINATION
        return result

    my_index = next((j for j, p in enumerate(path) if p.stop is not None and p.stop.id == rp.route_stop_id), None)
    if my_index is None:
        result["phase"] = Phase.APPROACHING
        return result

    remaining = cum[my_index] - along
    if remaining < -REACHED_TOLERANCE_M * 3:
        result["phase"] = Phase.PASSED
        return result

    stops_before = sum(1 for j in pending if j < my_index)
    # Velocidade média; se a van informar velocidade maior (via expressa, simulação), usa ela.
    speed_mps = max(_setting("LIVE_AVERAGE_SPEED_KMH", 25) / 3.6, location.speed or 0)
    seconds = max(0.0, remaining) / speed_mps + stops_before * _setting("LIVE_STOP_DWELL_SECONDS", 60)
    result["eta"] = {
        "minutes": max(1, math.ceil(seconds / 60)) if remaining > REACHED_TOLERANCE_M else 0,
        "distance_meters": max(0, round(remaining)),
        "stops_before": stops_before,
    }
    result["phase"] = Phase.ARRIVING if remaining <= arriving_m else Phase.APPROACHING
    return result
