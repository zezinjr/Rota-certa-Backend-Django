from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import (
    Address,
    Company,
    MeetingPoint,
    Person,
    Route,
    RouteEvent,
    RoutePassenger,
    RouteStop,
    Schedule,
    Vehicle,
)

PASSWORD = "Senha@Teste123"


# Sem chave do Google: os testes nunca chamam a Routes API de verdade.
@override_settings(ACCESS_ACCOUNT_AUTO_INITIAL_PASSWORD=PASSWORD, GOOGLE_MAPS_API_KEY="")
class EmployeeAppApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company = Company.objects.create(name="Acme", email_domain="acme.com")
        Address.objects.create(
            company=self.company, street="Av. Destino", number="1", city="Manaus",
            state="AM", zip_code="69000-000",
            latitude=Decimal("-3.1"), longitude=Decimal("-60.0"),
        )
        stop_addr = Address.objects.create(
            company=self.company, street="Rua Ponto", number="10", city="Manaus",
            state="AM", zip_code="69000-001",
            latitude=Decimal("-3.2"), longitude=Decimal("-60.1"),
        )
        point = MeetingPoint.objects.create(company=self.company, name="Ponto A", address=stop_addr)
        self.driver = Person.objects.create(
            company=self.company, name="Motorista", phone="9299", type="DRIVER",
            license_number="CNH1",
        )
        self.employee = Person.objects.create(
            company=self.company, name="Colab", phone="9288", type="EMPLOYEE",
            employee_code="E1",
        )
        other = Person.objects.create(
            company=self.company, name="Outro", phone="9277", type="EMPLOYEE",
            employee_code="E2",
        )
        vehicle = Vehicle.objects.create(
            company=self.company, driver=self.driver, plate_number="ABC1234",
            model="Van", capacity=15,
        )
        route = Route.objects.create(company=self.company, name="Rota 1", vehicle=vehicle)
        stop = RouteStop.objects.create(route=route, meeting_point=point, sequence=0)
        self.trip = RoutePassenger.objects.create(person=self.employee, route=route, route_stop=stop)
        self.other_trip = RoutePassenger.objects.create(person=other, route=route, route_stop=stop)
        Schedule.objects.create(company=self.company, weekdays=["MON"], time="06:30")
        RouteEvent.objects.create(
            route=route, event_type="departure", description="Saiu",
            latitude=Decimal("-3.3"), longitude=Decimal("-60.2"),
        )

    def login(self, email):
        res = self.client.post("/api/auth/login/", {"email": email, "password": PASSWORD}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access_token']}")

    def test_requires_authentication(self):
        self.assertEqual(self.client.get("/api/me/trips/").status_code, 401)

    def test_driver_is_forbidden(self):
        self.login("cnh1@acme.com")
        self.assertEqual(self.client.get("/api/me/trips/").status_code, 403)

    def test_profile(self):
        self.login("e1@acme.com")
        res = self.client.get("/api/me/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["employee_code"], "E1")
        self.assertEqual(res.data["company_name"], "Acme")

    def test_trips_payload(self):
        self.login("e1@acme.com")
        res = self.client.get("/api/me/trips/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        trip = res.data[0]
        self.assertEqual(trip["id"], self.trip.id)
        self.assertEqual(trip["route"]["status"], "in_route")
        self.assertEqual(trip["driver"]["name"], "Motorista")
        self.assertEqual(trip["vehicle"]["plate_number"], "ABC1234")
        self.assertEqual(trip["my_stop"]["title"], "Ponto A")
        self.assertEqual(trip["destination"]["label"], "Av. Destino, 1 — Manaus/AM")
        self.assertEqual(trip["schedules"][0]["time"], "06:30")
        self.assertEqual(len(trip["events"]), 1)

    def test_update_boarding_status(self):
        self.login("e1@acme.com")
        url = f"/api/me/trips/{self.trip.id}/boarding/"
        res = self.client.post(url, {"status": "absent"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.trip.refresh_from_db()
        self.assertEqual(self.trip.boarding_status, "absent")
        self.assertEqual(self.client.post(url, {"status": "xyz"}, format="json").status_code, 400)

    def test_cannot_touch_other_employee_trip(self):
        self.login("e1@acme.com")
        res = self.client.post(
            f"/api/me/trips/{self.other_trip.id}/boarding/", {"status": "absent"}, format="json"
        )
        self.assertEqual(res.status_code, 404)
        self.assertEqual(self.client.get(f"/api/me/trips/{self.other_trip.id}/").status_code, 404)


# Sem chave do Google: os testes nunca chamam a Routes API de verdade.
@override_settings(ACCESS_ACCOUNT_AUTO_INITIAL_PASSWORD=PASSWORD, GOOGLE_MAPS_API_KEY="")
class ApiAccessControlTests(TestCase):
    """Login obrigatório em toda a API; CRUD só para gestores; motorista limitado às próprias rotas."""

    def setUp(self):
        self.client = APIClient()
        self.company = Company.objects.create(name="Acme", email_domain="acme.com")
        addr = Address.objects.create(
            company=self.company, street="Rua", number="1", city="Manaus", state="AM",
            zip_code="69000-000", latitude=Decimal("-3.1"), longitude=Decimal("-60.0"),
        )
        point = MeetingPoint.objects.create(company=self.company, name="Ponto", address=addr)
        Person.objects.create(company=self.company, name="Gestora", phone="9200", type="MANAGER", employee_code="G1")
        self.driver = Person.objects.create(
            company=self.company, name="Motorista", phone="9201", type="DRIVER", license_number="CNH1",
        )
        other_driver = Person.objects.create(
            company=self.company, name="Outro", phone="9202", type="DRIVER", license_number="CNH2",
        )
        employee = Person.objects.create(
            company=self.company, name="Colab", phone="9203", type="EMPLOYEE", employee_code="E1",
        )
        own_vehicle = Vehicle.objects.create(company=self.company, driver=self.driver, plate_number="AAA1", model="Van", capacity=15)
        other_vehicle = Vehicle.objects.create(company=self.company, driver=other_driver, plate_number="BBB2", model="Van", capacity=15)
        self.own_route = Route.objects.create(company=self.company, name="Minha", vehicle=own_vehicle)
        self.other_route = Route.objects.create(company=self.company, name="Outra", vehicle=other_vehicle)
        stop = RouteStop.objects.create(route=self.own_route, meeting_point=point, sequence=0)
        self.own_passenger = RoutePassenger.objects.create(person=employee, route=self.own_route, route_stop=stop)
        RouteEvent.objects.create(route=self.other_route, event_type="stop", latitude=Decimal("-3"), longitude=Decimal("-60"))

    def login(self, email):
        self.client.credentials()
        res = self.client.post("/api/auth/login/", {"email": email, "password": PASSWORD}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access_token']}")

    def test_anonymous_gets_401_everywhere(self):
        for url in ["/api/companies/", "/api/people/", "/api/routes/", "/api/route-events/", "/api/vehicles/"]:
            self.assertEqual(self.client.get(url).status_code, 401, url)

    def test_login_stays_public(self):
        res = self.client.post("/api/auth/login/", {"email": "g1@acme.com", "password": PASSWORD}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["person"]["type"], "MANAGER")

    def test_manager_has_full_access(self):
        self.login("g1@acme.com")
        self.assertEqual(self.client.get("/api/companies/").status_code, 200)
        res = self.client.post("/api/companies/", {"name": "Nova"}, format="json")
        self.assertEqual(res.status_code, 201, res.data)

    def test_employee_and_driver_cannot_use_admin_endpoints(self):
        for email in ["e1@acme.com", "cnh1@acme.com"]:
            self.login(email)
            self.assertEqual(self.client.get("/api/companies/").status_code, 403, email)
            self.assertEqual(self.client.post("/api/companies/", {"name": "X"}, format="json").status_code, 403, email)

    def test_driver_sees_and_creates_events_only_for_own_routes(self):
        self.login("cnh1@acme.com")
        self.assertEqual(self.client.get("/api/route-events/").data["count"], 0)
        payload = {"event_type": "departure", "latitude": "-3.1", "longitude": "-60.0"}
        res = self.client.post("/api/route-events/", {**payload, "route": self.own_route.id}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        res = self.client.post("/api/route-events/", {**payload, "route": self.other_route.id}, format="json")
        self.assertEqual(res.status_code, 403)

    def test_driver_updates_only_boarding_status_of_own_passengers(self):
        self.login("cnh1@acme.com")
        url = f"/api/route-passengers/{self.own_passenger.id}/"
        self.assertEqual(self.client.patch(url, {"boarding_status": "confirmed"}, format="json").status_code, 200)
        self.own_passenger.refresh_from_db()
        self.assertEqual(self.own_passenger.boarding_status, "confirmed")
        self.assertEqual(self.client.patch(url, {"route": self.other_route.id}, format="json").status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 403)

    def test_employee_cannot_use_driver_scoped_endpoints(self):
        self.login("e1@acme.com")
        self.assertEqual(self.client.get("/api/route-events/").status_code, 403)

    def test_manager_requires_employee_code(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            Person.objects.create(company=self.company, name="Sem código", phone="1", type="MANAGER")


# Sem chave do Google: os testes nunca chamam a Routes API de verdade.
@override_settings(ACCESS_ACCOUNT_AUTO_INITIAL_PASSWORD=PASSWORD, GOOGLE_MAPS_API_KEY="")
class LineRouteTestBase(TestCase):
    """
    Rota reta no sentido leste-oeste: paradas a cada 0,01° de longitude (~1,1 km)
    e a empresa no fim. O colaborador embarca na 3ª parada (sequence 2).
    """

    LAT = Decimal("-3.100000")

    def lng(self, value):
        return Decimal(str(value))

    def setUp(self):
        from .models import VehicleLocation  # noqa: F401  (garante o model carregado)

        self.client = APIClient()
        self.company = Company.objects.create(name="Acme", email_domain="acme.com")
        Address.objects.create(  # empresa (destino)
            company=self.company, street="Empresa", number="1", city="Manaus", state="AM",
            zip_code="69000-000", latitude=self.LAT, longitude=self.lng(-60.04),
        )
        self.driver = Person.objects.create(
            company=self.company, name="Motorista", phone="9201", type="DRIVER", license_number="CNH1",
        )
        other_driver = Person.objects.create(
            company=self.company, name="Outro", phone="9202", type="DRIVER", license_number="CNH2",
        )
        self.employee = Person.objects.create(
            company=self.company, name="Colab", phone="9203", type="EMPLOYEE", employee_code="E1",
        )
        other_employee = Person.objects.create(
            company=self.company, name="Colab 2", phone="9204", type="EMPLOYEE", employee_code="E2",
        )
        self.vehicle = Vehicle.objects.create(company=self.company, driver=self.driver, plate_number="AAA1", model="Van", capacity=15)
        other_vehicle = Vehicle.objects.create(company=self.company, driver=other_driver, plate_number="BBB2", model="Van", capacity=15)
        self.route = Route.objects.create(company=self.company, name="Rota reta", vehicle=self.vehicle)
        self.other_route = Route.objects.create(company=self.company, name="Outra", vehicle=other_vehicle)
        stops = []
        for seq, lng in enumerate([-60.00, -60.01, -60.02, -60.03]):
            addr = Address.objects.create(
                company=self.company, street=f"Ponto {seq}", number="1", city="Manaus", state="AM",
                zip_code="69000-001", latitude=self.LAT, longitude=self.lng(lng),
            )
            point = MeetingPoint.objects.create(company=self.company, name=f"Ponto {seq}", address=addr)
            stops.append(RouteStop.objects.create(route=self.route, meeting_point=point, sequence=seq))
        self.trip = RoutePassenger.objects.create(person=self.employee, route=self.route, route_stop=stops[2])
        self.other_trip = RoutePassenger.objects.create(person=other_employee, route=self.other_route)

    def login(self, email):
        self.client.credentials()
        res = self.client.post("/api/auth/login/", {"email": email, "password": PASSWORD}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access_token']}")

    def send(self, lng, **extra):
        return self.client.post(
            f"/api/routes/{self.route.id}/location/",
            {"latitude": str(self.LAT), "longitude": str(lng), **extra},
            format="json",
        )

    def live(self):
        self.login("e1@acme.com")
        res = self.client.get(f"/api/me/trips/{self.trip.id}/live/")
        self.assertEqual(res.status_code, 200)
        return res.data



@override_settings(ACCESS_ACCOUNT_AUTO_INITIAL_PASSWORD=PASSWORD)
class LiveTrackingTests(LineRouteTestBase):
    # --- envio do GPS pelo motorista

    def test_driver_sends_location_for_own_route(self):
        self.login("cnh1@acme.com")
        res = self.send(-60.005, heading=270, speed=8.5)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertAlmostEqual(res.data["progress_meters"], 555, delta=10)
        self.assertEqual(self.vehicle.location.route_id, self.route.id)

    def test_driver_cannot_send_location_for_other_route(self):
        self.login("cnh1@acme.com")
        res = self.client.post(f"/api/routes/{self.other_route.id}/location/", {"latitude": "-3.1", "longitude": "-60"}, format="json")
        self.assertEqual(res.status_code, 404)

    def test_location_validation_and_permissions(self):
        self.login("cnh1@acme.com")
        self.assertEqual(self.send(-60.0, heading=400).status_code, 400)
        self.login("e1@acme.com")
        self.assertEqual(self.send(-60.0).status_code, 403)

    # --- situação ao vivo para o colaborador

    def test_waiting_without_location(self):
        data = self.live()
        self.assertFalse(data["is_live"])
        self.assertEqual(data["phase"], "waiting")
        self.assertIsNone(data["vehicle"])

    def test_approaching_with_eta_and_stops_before(self):
        self.login("cnh1@acme.com")
        self.send(-60.005)  # meio do caminho entre a 1ª e a 2ª parada
        data = self.live()
        self.assertTrue(data["is_live"])
        self.assertEqual(data["phase"], "approaching")
        self.assertEqual(data["next_stop_sequence"], 1)
        self.assertEqual(data["eta"]["stops_before"], 1)
        self.assertAlmostEqual(data["eta"]["distance_meters"], 1665, delta=15)
        # 1665 m a 25 km/h (~240 s) + 60 s na parada anterior = ~5 min
        self.assertEqual(data["eta"]["minutes"], 5)
        self.assertEqual(data["path_progress"]["segment"], 0)

    def test_phases_along_the_route(self):
        self.login("cnh1@acme.com")
        expected = [(-60.019, "arriving"), (-60.025, "passed"), (-60.0395, "at_destination")]
        for lng, phase in expected:
            self.send(lng)
            self.assertEqual(self.live()["phase"], phase, lng)
            self.login("cnh1@acme.com")

    def test_stale_location_is_not_live(self):
        from datetime import timedelta
        from django.utils import timezone
        from .live import save_vehicle_location

        save_vehicle_location(self.vehicle, self.route, self.LAT, -60.005, recorded_at=timezone.now() - timedelta(minutes=10))
        data = self.live()
        self.assertFalse(data["is_live"])
        self.assertIsNotNone(data["vehicle"])
        self.assertIsNone(data["eta"])

    def test_cannot_see_other_passenger_live(self):
        self.login("e1@acme.com")
        self.assertEqual(self.client.get(f"/api/me/trips/{self.other_trip.id}/live/").status_code, 404)

    def test_trip_payload_uses_latest_gps_position(self):
        self.login("cnh1@acme.com")
        self.send(-60.005)
        self.login("e1@acme.com")
        trip = self.client.get("/api/me/trips/").data[0]
        self.assertAlmostEqual(float(trip["last_position"]["longitude"]), -60.005, places=5)

    # --- trajeto que se cruza

    def test_progress_keeps_continuity_on_crossing_paths(self):
        from .live import PathPoint, cumulative_distances, locate_on_path

        # A→B vai para o leste; C→D desce e cruza A→B no meio.
        path = [PathPoint(0, 0), PathPoint(0, 0.02), PathPoint(0.01, 0.01), PathPoint(-0.01, 0.01)]
        cum = cumulative_distances(path)
        crossing = (0.0, 0.01)
        first_pass = locate_on_path(crossing, path, cum, previous_along=cum[0] + 900)
        second_pass = locate_on_path(crossing, path, cum, previous_along=cum[2] + 900)
        self.assertLess(first_pass, cum[1])   # ainda no 1º trecho
        self.assertGreater(second_pass, cum[2])  # já no trecho que cruza


class TrackingPageTests(TestCase):
    def test_tracking_page_is_public_and_uses_the_location_endpoint(self):
        res = self.client.get("/rastreamento/")
        self.assertEqual(res.status_code, 200)
        html = res.content.decode()
        self.assertIn("Rastreamento do motorista", html)
        self.assertIn("/location/", html)
        self.assertIn("watchPosition", html)


class FakeRoutesResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        import json
        return json.dumps(self.payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@override_settings(ACCESS_ACCOUNT_AUTO_INITIAL_PASSWORD=PASSWORD, GOOGLE_MAPS_API_KEY="test-key")
class RoadPathTests(LineRouteTestBase):
    """Trajeto pelas ruas com a Routes API simulada: cada trecho contorna o quarteirão (sobe 0,005° e desce)."""

    LNGS = [-60.00, -60.01, -60.02, -60.03, -60.04]  # 4 paradas + empresa

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        super().setUp()

    def fake_response(self, *args, **kwargs):
        from .road_path import encode_polyline
        lat, top = float(self.LAT), float(self.LAT) + 0.005
        legs = []
        for a, b in zip(self.LNGS, self.LNGS[1:]):
            legs.append({"distanceMeters": 2220, "polyline": {"encodedPolyline": encode_polyline(
                [(lat, a), (top, a), (top, b), (lat, b)])}})
        return FakeRoutesResponse({"routes": [{"distanceMeters": 2220 * 4, "legs": legs}]})

    def patch_api(self, **kwargs):
        from unittest import mock
        return mock.patch("core.road_path.urllib.request.urlopen", side_effect=kwargs.get("side_effect", self.fake_response))

    def test_without_key_uses_straight_line_and_never_calls_api(self):
        with override_settings(GOOGLE_MAPS_API_KEY=""), self.patch_api() as api:
            self.login("e1@acme.com")
            trip = self.client.get("/api/me/trips/").data[0]
        self.assertEqual(trip["path"]["source"], "straight")
        api.assert_not_called()

    def test_blocked_key_logs_reason_and_hint(self):
        import io
        import urllib.error

        from .live import route_waypoints
        from .road_path import get_road_path

        body = (b'{"error": {"code": 403, "status": "PERMISSION_DENIED", "message": "Requests are blocked.", '
                b'"details": [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": "API_KEY_SERVICE_BLOCKED"}]}}')
        error = urllib.error.HTTPError("https://routes", 403, "Forbidden", {}, io.BytesIO(body))
        waypoints = [(p.lat, p.lng) for p in route_waypoints(self.route)]
        with self.patch_api(side_effect=error), self.assertLogs("core.road_path", "WARNING") as logs:
            self.assertIsNone(get_road_path(self.route, waypoints))
        self.assertIn("API_KEY_SERVICE_BLOCKED", logs.output[0])
        self.assertIn("Restrições de API", logs.output[0])

    def test_road_path_is_fetched_once_and_cached_on_the_route(self):
        with self.patch_api() as api:
            self.login("e1@acme.com")
            trip = self.client.get("/api/me/trips/").data[0]
            self.client.get("/api/me/trips/")
            self.client.get(f"/api/me/trips/{self.trip.id}/live/")
        self.assertEqual(api.call_count, 1)
        self.assertEqual(trip["path"]["source"], "google")
        self.route.refresh_from_db()
        self.assertEqual(self.route.road_path["stop_indexes"], [0, 3, 6, 9, 12])

    def test_eta_uses_the_distance_along_the_streets(self):
        with self.patch_api():
            self.login("cnh1@acme.com")
            self.client.post(
                f"/api/routes/{self.route.id}/location/",
                {"latitude": str(float(self.LAT) + 0.005), "longitude": "-60.005"}, format="json")
            data = self.live()
            trip = self.client.get("/api/me/trips/").data[0]
        # topo do 1º quarteirão: ~1110 m andados; parada 3 fica a 2 × 2220 m → faltam ~3330 m pelas ruas
        self.assertAlmostEqual(data["eta"]["distance_meters"], 3330, delta=40)
        self.assertEqual(data["eta"]["stops_before"], 1)
        self.assertEqual(data["path_progress"]["path_version"], trip["path"]["version"])

    def test_changing_stops_recomputes_the_path(self):
        with self.patch_api() as api:
            self.login("e1@acme.com")
            self.client.get("/api/me/trips/")
            stop = self.route.stops.get(sequence=1)
            stop.meeting_point.address.latitude = Decimal("-3.101000")
            stop.meeting_point.address.save()
            self.client.get("/api/me/trips/")
        self.assertEqual(api.call_count, 2)

    def test_api_failure_falls_back_to_straight_line_and_backs_off(self):
        import urllib.error
        with self.patch_api(side_effect=urllib.error.URLError("offline")) as api:
            self.login("e1@acme.com")
            first = self.client.get("/api/me/trips/").data[0]
            self.client.get("/api/me/trips/")
        self.assertEqual(first["path"]["source"], "straight")
        self.assertEqual(api.call_count, 1)  # não tenta de novo por 10 min

    def test_polyline_codec_matches_google_reference(self):
        from .road_path import decode_polyline, encode_polyline
        points = [(38.5, -120.2), (40.7, -120.95), (43.252, -126.453)]
        self.assertEqual(encode_polyline(points), "_p~iF~ps|U_ulLnnqC_mqNvxq`@")
        self.assertEqual(decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@"), points)


@override_settings(
    GOOGLE_MAPS_API_KEY="",
    WHATSAPP_TOKEN="test-token",
    WHATSAPP_PHONE_NUMBER_ID="12345",
    WHATSAPP_ASYNC=False,
    WHATSAPP_EVENTS="approaching,arriving",
    WHATSAPP_APPROACHING_MINUTES=5,
)
class WhatsAppNotificationTests(LineRouteTestBase):
    """Avisos pelo WhatsApp com a API da Meta simulada. O colaborador embarca em -60.02."""

    def setUp(self):
        super().setUp()
        self.employee.phone = "+55 (92) 99111-0000"
        self.employee.whatsapp_opt_in = True
        self.employee.save()
        self.sent = []

    def fake_meta(self, request, *args, **kwargs):
        import json
        self.sent.append(json.loads(request.data))
        return FakeRoutesResponse({"messages": [{"id": f"wamid.{len(self.sent)}"}]})

    def drive(self, *lngs):
        from unittest import mock
        self.login("cnh1@acme.com")
        with mock.patch("core.whatsapp.urllib.request.urlopen", side_effect=self.fake_meta):
            for lng in lngs:
                with self.captureOnCommitCallbacks(execute=True):
                    self.assertEqual(self.send(lng).status_code, 200)

    def test_profile_opt_in_toggle(self):
        self.employee.whatsapp_opt_in = False
        self.employee.save()
        self.login("e1@acme.com")
        me = self.client.get("/api/me/").data
        self.assertFalse(me["whatsapp_opt_in"])
        self.assertTrue(me["whatsapp_available"])
        res = self.client.patch("/api/me/", {"whatsapp_opt_in": True}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertTrue(res.data["whatsapp_opt_in"])
        self.employee.refresh_from_db()
        self.assertIsNotNone(self.employee.whatsapp_opt_in_at)
        self.assertEqual(self.client.patch("/api/me/", {}, format="json").status_code, 400)

    def test_approaching_then_arriving_each_sent_once(self):
        from .models import Notification
        self.drive(-60.000)          # ~7 min do ponto: ainda não avisa
        self.assertEqual(self.sent, [])
        self.drive(-60.012, -60.013)  # ~3 min: avisa uma vez só
        self.drive(-60.018, -60.019)  # a menos de 300 m: "chegando", uma vez só
        self.assertEqual([m["template"]["name"] for m in self.sent], ["rota_van_a_caminho", "rota_van_chegando"])
        first = self.sent[0]
        self.assertEqual(first["to"], "5592991110000")
        self.assertEqual(first["template"]["language"]["code"], "pt_BR")
        params = [p["text"] for p in first["template"]["components"][0]["parameters"]]
        self.assertEqual(params[:3], ["Colab", "Rota reta", "Ponto 2"])
        self.assertTrue(1 <= int(params[3]) <= 5)
        self.assertEqual(
            set(Notification.objects.values_list("kind", "status")),
            {("approaching", "sent"), ("arriving", "sent")},
        )

    def test_no_message_without_opt_in_or_when_absent(self):
        self.employee.whatsapp_opt_in = False
        self.employee.save()
        self.drive(-60.015)
        self.employee.whatsapp_opt_in = True
        self.employee.save()
        self.trip.boarding_status = "absent"
        self.trip.save()
        self.drive(-60.016)
        self.assertEqual(self.sent, [])

    @override_settings(WHATSAPP_TOKEN="")
    def test_disabled_without_credentials(self):
        from .models import Notification
        self.drive(-60.015)
        self.assertEqual(self.sent, [])
        self.assertFalse(Notification.objects.exists())

    def test_meta_error_is_recorded(self):
        import io
        import urllib.error
        from unittest import mock

        from .models import Notification
        body = b'{"error": {"code": 132001, "message": "Template name does not exist in the translation"}}'
        error = urllib.error.HTTPError("https://graph", 404, "Not Found", {}, io.BytesIO(body))
        self.login("cnh1@acme.com")
        with mock.patch("core.whatsapp.urllib.request.urlopen", side_effect=error), \
                self.captureOnCommitCallbacks(execute=True):
            self.send(-60.015)
        notification = Notification.objects.get()
        self.assertEqual(notification.status, "failed")
        self.assertIn("132001", notification.error)

    @override_settings(WHATSAPP_EVENTS="departure")
    def test_departure_event_notifies_passengers(self):
        from unittest import mock

        from .models import RouteEvent
        with mock.patch("core.whatsapp.urllib.request.urlopen", side_effect=self.fake_meta), \
                self.captureOnCommitCallbacks(execute=True):
            RouteEvent.objects.create(route=self.route, event_type="departure", latitude=self.LAT, longitude=self.lng(-60.0))
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.sent[0]["template"]["name"], "rota_van_saiu")

    def test_normalize_phone(self):
        from .whatsapp import normalize_phone
        self.assertEqual(normalize_phone("(92) 99111-0000"), "5592991110000")
        self.assertEqual(normalize_phone("+1 415 555 0100"), "14155550100")
        self.assertEqual(normalize_phone("9203"), "")


@override_settings(
    GOOGLE_MAPS_API_KEY="",
    WHATSAPP_PROVIDER="evolution",
    WHATSAPP_TOKEN="",
    EVOLUTION_API_URL="http://evolution.test:8080/",
    EVOLUTION_API_KEY="evo-key",
    EVOLUTION_INSTANCE="rotacerta",
    WHATSAPP_ASYNC=False,
    WHATSAPP_EVENTS="approaching,arriving",
    WHATSAPP_APPROACHING_MINUTES=5,
)
class EvolutionWhatsAppTests(WhatsAppNotificationTests):
    """Os mesmos avisos pela Evolution API: texto livre em /message/sendText/{instância}."""

    def fake_meta(self, request, *args, **kwargs):
        import json
        self.requests.append(request)
        self.sent.append(json.loads(request.data))
        return FakeRoutesResponse({"key": {"id": f"evo.{len(self.sent)}"}, "status": "PENDING"})

    def setUp(self):
        super().setUp()
        self.requests = []

    def test_approaching_then_arriving_each_sent_once(self):
        from .models import Notification
        self.drive(-60.000, -60.012, -60.013, -60.018, -60.019)
        self.assertEqual(len(self.sent), 2)
        first, second = self.sent
        self.assertEqual(first["number"], "5592991110000")
        self.assertRegex(first["text"], r"^Olá, Colab! A van da Rota reta chega ao seu ponto \(Ponto 2\) em cerca de [1-5] minutos\.$")
        self.assertEqual(second["text"], "Olá, Colab! A van da Rota reta está chegando ao seu ponto (Ponto 2). Prepare-se para embarcar.")
        request = self.requests[0]
        self.assertEqual(request.full_url, "http://evolution.test:8080/message/sendText/rotacerta")
        self.assertEqual(request.get_header("Apikey"), "evo-key")
        self.assertEqual(set(Notification.objects.values_list("status", flat=True)), {"sent"})

    def test_departure_event_notifies_passengers(self):
        from unittest import mock

        from .models import RouteEvent
        with override_settings(WHATSAPP_EVENTS="departure"), \
                mock.patch("core.whatsapp.urllib.request.urlopen", side_effect=self.fake_meta), \
                self.captureOnCommitCallbacks(execute=True):
            RouteEvent.objects.create(route=self.route, event_type="departure", latitude=self.LAT, longitude=self.lng(-60.0))
        self.assertEqual(len(self.sent), 1)
        self.assertIn("saiu e já está a caminho", self.sent[0]["text"])

    @override_settings(EVOLUTION_API_KEY="")
    def test_disabled_without_credentials(self):
        from .models import Notification
        self.drive(-60.015)
        self.assertEqual(self.sent, [])
        self.assertFalse(Notification.objects.exists())

    def test_meta_error_is_recorded(self):
        import io
        import urllib.error
        from unittest import mock

        from .models import Notification
        body = b'{"status": 400, "error": "Bad Request", "response": {"message": [{"exists": false, "number": "5592991110000"}]}}'
        error = urllib.error.HTTPError("http://evolution.test", 400, "Bad Request", {}, io.BytesIO(body))
        self.login("cnh1@acme.com")
        with mock.patch("core.whatsapp.urllib.request.urlopen", side_effect=error), \
                self.captureOnCommitCallbacks(execute=True):
            self.send(-60.015)
        notification = Notification.objects.get()
        self.assertEqual(notification.status, "failed")
        self.assertIn('"exists": false', notification.error)

    def test_connect_command_creates_instance_and_saves_qr_code(self):
        import base64
        import io
        import json
        import os
        import tempfile
        import urllib.error
        from unittest import mock

        from django.core.management import call_command

        png = base64.b64encode(b"\x89PNG fake").decode()
        calls = []

        def fake(request, *args, **kwargs):
            calls.append((request.get_method(), request.full_url))
            if "connectionState" in request.full_url:
                raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, io.BytesIO(
                    b'{"status": 404, "response": {"message": ["The \\"rotacerta\\" instance does not exist"]}}'))
            if request.full_url.endswith("instance/create"):
                self.assertEqual(json.loads(request.data)["integration"], "WHATSAPP-BAILEYS")
                return FakeRoutesResponse({"instance": {"instanceName": "rotacerta"}})
            return FakeRoutesResponse({"pairingCode": None, "code": "2@abc", "base64": f"data:image/png;base64,{png}"})

        with tempfile.TemporaryDirectory() as tmp, mock.patch("core.whatsapp.urllib.request.urlopen", side_effect=fake):
            path = os.path.join(tmp, "qr.png")
            call_command("conectar_whatsapp", arquivo=path, aguardar=0, stdout=io.StringIO())
            with open(path, "rb") as fh:
                self.assertEqual(fh.read(), b"\x89PNG fake")
        self.assertEqual([m for m, _ in calls], ["GET", "POST", "GET"])
        self.assertTrue(calls[2][1].endswith("/instance/connect/rotacerta"))
