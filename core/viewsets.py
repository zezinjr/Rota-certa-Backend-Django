import json
import urllib.error
import urllib.request

from django.conf import settings
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.filters import OrderingFilter

from .models import (
    Company,
    Person,
    Route,
    RouteStop,
    RouteEvent,
    Schedule,
    Address,
    MeetingPoint,
    RoutePassenger,
    Vehicle,
)
from .serializers import (
    CompanySerializer,
    PersonSerializer,
    RouteSerializer,
    RouteStopSerializer,
    ScheduleSerializer,
    AddressSerializer,
    MeetingPointSerializer,
    DriverSerializer,
    EmployeeSerializer,
    RoutePassengerSerializer,
    RouteEventSerializer,
    VehicleSerializer,
)
from .driver_serializers import DriverRouteBoardSerializer
from .permissions import IsDriver, IsManagerOrDriver
from .filters import (
    CompanyFilter,
    PersonFilter,
    DriverFilter,
    EmployeeFilter,
    RouteFilter,
    ScheduleFilter,
    MeetingPointFilter,
    RouteEventFilter,
    RoutePassengerFilter,
    VehicleFilter,
    RouteStopFilter,
)


class BaseViewSet(viewsets.ModelViewSet):
    """
    - Lista apenas registros ativos por padrão
    - DELETE remove do banco (sem soft delete)
    """

    filter_backends = [DjangoFilterBackend]

    def get_queryset(self):
        qs = super().get_queryset()
        if hasattr(self.queryset.model, "is_active"):
            return qs.filter(is_active=True)
        return qs


class CompanyViewSet(BaseViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    filterset_class = CompanyFilter


class PersonViewSet(BaseViewSet):
    queryset = Person.objects.select_related("company")
    serializer_class = PersonSerializer
    filterset_class = PersonFilter


class RouteViewSet(BaseViewSet):
    queryset = Route.objects.select_related("company", "vehicle")
    serializer_class = RouteSerializer
    filterset_class = RouteFilter

    @action(
        detail=False,
        methods=["get"],
        url_path="my-routes",
        permission_classes=[IsAuthenticated, IsDriver],
    )
    def my_routes(self, request):
        person = request.user.person
        qs = (
            Route.objects.filter(is_active=True, vehicle__driver=person)
            .select_related("company", "vehicle")
            .prefetch_related(
                Prefetch(
                    "stops",
                    queryset=RouteStop.objects.filter(is_active=True)
                    .select_related("meeting_point", "meeting_point__address")
                    .order_by("sequence"),
                ),
                Prefetch(
                    "route_passengers",
                    queryset=RoutePassenger.objects.filter(is_active=True).select_related(
                        "person", "route_stop", "route_stop__meeting_point"
                    ),
                ),
                Prefetch(
                    "events",
                    queryset=RouteEvent.objects.order_by("-timestamp"),
                ),
            )
            .order_by("id")
        )
        ser = DriverRouteBoardSerializer()
        return Response([ser.to_representation(r) for r in qs])

    @action(
        detail=True,
        methods=["get"],
        url_path="driver-detail",
        permission_classes=[IsAuthenticated, IsDriver],
    )
    def driver_detail(self, request, pk=None):
        person = request.user.person
        route = get_object_or_404(
            Route.objects.filter(is_active=True, vehicle__driver=person)
            .select_related("company", "vehicle")
            .prefetch_related(
                Prefetch(
                    "stops",
                    queryset=RouteStop.objects.filter(is_active=True)
                    .select_related("meeting_point", "meeting_point__address")
                    .order_by("sequence"),
                ),
                Prefetch(
                    "route_passengers",
                    queryset=RoutePassenger.objects.filter(is_active=True).select_related(
                        "person", "route_stop", "route_stop__meeting_point"
                    ),
                ),
                Prefetch(
                    "events",
                    queryset=RouteEvent.objects.order_by("-timestamp"),
                ),
            ),
            pk=pk,
        )
        return Response(DriverRouteBoardSerializer().to_representation(route))

    @action(detail=True, methods=["get"])
    def events(self, request, pk=None):
        route = self.get_object()
        qs = route.events.order_by("-timestamp")
        serializer = RouteEventSerializer(qs, many=True)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["get"],
        url_path="navigation",
        permission_classes=[IsAuthenticated],
    )
    def navigation(self, request, pk=None):
        person = request.user.person
        print(
            "[route-navigation]",
            f"account_id={getattr(request.user, 'id', None)}",
            f"person_id={person.id}",
            f"person_type={person.type}",
            f"route_id={pk}",
        )

        if person.type != Person.PersonType.DRIVER:
            return Response(
                {
                    "detail": "Apenas motoristas podem acessar este recurso.",
                    "person_id": person.id,
                    "person_type": person.type,
                    "route_id": pk,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        route = get_object_or_404(
            Route.objects.filter(is_active=True, vehicle__driver=person)
            .select_related("company", "vehicle")
            .prefetch_related(
                Prefetch(
                    "stops",
                    queryset=RouteStop.objects.filter(is_active=True)
                    .select_related("meeting_point", "meeting_point__address")
                    .order_by("sequence"),
                )
            ),
            pk=pk,
        )

        if not settings.GOOGLE_MAPS_API_KEY:
            return Response(
                {"detail": "GOOGLE_MAPS_API_KEY não configurada."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        origin = _address_to_location(
            Address.objects.filter(is_active=True, person=person).first()
        )
        destination = _address_to_location(
            Address.objects.filter(
                is_active=True,
                person__isnull=True,
                company=route.company,
            )
            .exclude(
                id__in=route.stops.values_list(
                    "meeting_point__address_id",
                    flat=True,
                )
            )
            .first()
        )
        stops = [
            _address_to_location(stop.meeting_point.address)
            for stop in route.stops.all()
            if stop.meeting_point and stop.meeting_point.address
        ]
        stops = [stop for stop in stops if stop is not None]

        if origin is None or destination is None:
            return Response(
                {"detail": "Origem ou destino da rota sem coordenadas."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            google_payload = _compute_google_route(
                origin=origin,
                destination=destination,
                intermediates=stops,
            )
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            return Response(
                {"detail": "Falha ao calcular rota no Google.", "error": body},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except urllib.error.URLError as exc:
            return Response(
                {"detail": "Google Routes API indisponível.", "error": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        route_data = (google_payload.get("routes") or [{}])[0]
        polyline = route_data.get("polyline") or {}
        legs = route_data.get("legs") or []
        first_step = _first_navigation_step(legs)

        return Response(
            {
                "route": route.id,
                "encoded_polyline": polyline.get("encodedPolyline", ""),
                "duration": route_data.get("duration"),
                "duration_text": _format_duration(route_data.get("duration")),
                "distance_meters": route_data.get("distanceMeters"),
                "distance_text": _format_distance(route_data.get("distanceMeters")),
                "instruction": first_step,
                "waypoints": {
                    "origin": origin,
                    "intermediates": stops,
                    "destination": destination,
                },
            }
        )


class ScheduleViewSet(BaseViewSet):
    queryset = Schedule.objects.select_related("company")
    serializer_class = ScheduleSerializer
    filterset_class = ScheduleFilter


class AddressViewSet(BaseViewSet):
    queryset = Address.objects.all()
    serializer_class = AddressSerializer


class MeetingPointViewSet(BaseViewSet):
    queryset = MeetingPoint.objects.select_related("company", "address")
    serializer_class = MeetingPointSerializer
    filterset_class = MeetingPointFilter


class DriverViewSet(BaseViewSet):
    queryset = Person.objects.filter(type="DRIVER").select_related("company")
    serializer_class = DriverSerializer
    filterset_class = DriverFilter


class EmployeeViewSet(BaseViewSet):
    queryset = Person.objects.filter(type="EMPLOYEE").select_related("company")
    serializer_class = EmployeeSerializer
    filterset_class = EmployeeFilter


class DriverScopedMixin:
    """
    Gestores têm acesso total (permissão padrão). Motoristas podem usar apenas
    `driver_actions`, e só sobre registros das rotas em que dirigem o veículo.
    """

    driver_actions: set = set()

    def _driver(self):
        person = getattr(self.request.user, "person", None)
        if person is not None and person.type == Person.PersonType.DRIVER:
            return person
        return None

    def get_permissions(self):
        if self.action in self.driver_actions:
            return [IsAuthenticated(), IsManagerOrDriver()]
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        driver = self._driver()
        if driver is not None:
            qs = qs.filter(route__vehicle__driver=driver)
        return qs


class RoutePassengerViewSet(DriverScopedMixin, BaseViewSet):
    queryset = RoutePassenger.objects.select_related("person", "route", "route_stop")
    serializer_class = RoutePassengerSerializer
    filterset_class = RoutePassengerFilter
    # Motorista: consultar passageiros e marcar embarque (somente boarding_status).
    driver_actions = {"list", "retrieve", "partial_update"}

    def partial_update(self, request, *args, **kwargs):
        if self._driver() is not None and set(request.data) - {"boarding_status"}:
            raise PermissionDenied("Motoristas só podem alterar o boarding_status.")
        return super().partial_update(request, *args, **kwargs)


class RouteStopViewSet(BaseViewSet):
    queryset = RouteStop.objects.select_related("route", "meeting_point", "meeting_point__address")
    serializer_class = RouteStopSerializer
    filterset_class = RouteStopFilter


class RouteEventViewSet(DriverScopedMixin, BaseViewSet):
    queryset = RouteEvent.objects.select_related("route")
    serializer_class = RouteEventSerializer
    # Motorista: registrar saída/parada/atraso/chegada das próprias rotas
    # (é o que atualiza o status visto no app do colaborador).
    driver_actions = {"list", "retrieve", "create"}

    def perform_create(self, serializer):
        driver = self._driver()
        route = serializer.validated_data["route"]
        if driver is not None and (route.vehicle is None or route.vehicle.driver_id != driver.id):
            raise PermissionDenied("O motorista só pode registrar eventos das próprias rotas.")
        serializer.save()

    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = RouteEventFilter
    ordering_fields = ["timestamp", "event_type"]
    ordering = ["-timestamp"]

class VehicleViewSet(BaseViewSet):
    queryset = Vehicle.objects.select_related("company", "driver")
    serializer_class = VehicleSerializer
    filterset_class = VehicleFilter


def _address_to_location(address):
    if not address or address.latitude is None or address.longitude is None:
        return None

    return {
        "latitude": float(address.latitude),
        "longitude": float(address.longitude),
    }


def _compute_google_route(origin, destination, intermediates):
    payload = {
        "origin": {"location": {"latLng": origin}},
        "destination": {"location": {"latLng": destination}},
        "intermediates": [
            {"location": {"latLng": waypoint}}
            for waypoint in intermediates
        ],
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
        "computeAlternativeRoutes": False,
        "languageCode": "pt-BR",
        "units": "METRIC",
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        settings.GOOGLE_ROUTES_API_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": settings.GOOGLE_MAPS_API_KEY,
            "X-Goog-FieldMask": (
                "routes.duration,"
                "routes.distanceMeters,"
                "routes.polyline.encodedPolyline,"
                "routes.legs.steps.navigationInstruction"
            ),
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _first_navigation_step(legs):
    for leg in legs:
        for step in leg.get("steps") or []:
            instruction = step.get("navigationInstruction") or {}
            text = instruction.get("instructions")
            if text:
                return text
    return "Siga a rota"


def _format_duration(duration):
    if not duration or not isinstance(duration, str) or not duration.endswith("s"):
        return None

    try:
        seconds = int(float(duration[:-1]))
    except ValueError:
        return None

    minutes = max(1, round(seconds / 60))
    return f"{minutes} min"


def _format_distance(distance_meters):
    if distance_meters is None:
        return None

    try:
        meters = float(distance_meters)
    except (TypeError, ValueError):
        return None

    if meters >= 1000:
        return f"{meters / 1000:.1f} km"
    return f"{round(meters)} m"