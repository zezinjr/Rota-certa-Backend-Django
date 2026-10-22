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
