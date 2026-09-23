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


@override_settings(ACCESS_ACCOUNT_AUTO_INITIAL_PASSWORD=PASSWORD)
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
