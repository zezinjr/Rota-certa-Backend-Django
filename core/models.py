import re

from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


def normalize_email(email):
    if not email:
        return ""
    return str(email).strip().lower()


def derive_email_domain_from_company_name(name: str) -> str:
    """
    Gera um domínio estilo samsung.com a partir do nome da empresa
    (primeira palavra alfanumérica em minúsculas + .com).
    """
    name = (name or "").strip()
    if not name:
        return "empresa.com"
    parts = re.split(r"[\s.,_-]+", name)
    first = next((p for p in parts if p), "")
    slug = re.sub(r"[^a-z0-9]", "", first.lower())
    if not slug:
        slug = "empresa"
    return f"{slug}.com"


def normalize_email_domain(domain: str) -> str:
    if not domain:
        return ""
    d = str(domain).strip().lower().lstrip("@")
    return d

class ActiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)

class BaseModel(models.Model):
    id = models.BigAutoField(primary_key=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        abstract = True

class Company(BaseModel):
    name = models.CharField(max_length=255)
    email_domain = models.CharField(
        max_length=255,
        blank=True,
        help_text="Domínio dos e-mails automáticos, ex: samsung.com (sem @). "
        "Vazio = derivado do nome da empresa.",
    )

    def clean(self):
        super().clean()
        if self.email_domain:
            self.email_domain = normalize_email_domain(self.email_domain)

    def save(self, *args, **kwargs):
        if self.email_domain:
            self.email_domain = normalize_email_domain(self.email_domain)
        super().save(*args, **kwargs)

    def get_email_domain(self) -> str:
        if self.email_domain:
            return self.email_domain
        return derive_email_domain_from_company_name(self.name)

    def __str__(self):
        return self.name


class Person(BaseModel):
    class PersonType(models.TextChoices):
        DRIVER = "DRIVER", "Driver"
        EMPLOYEE = "EMPLOYEE", "Employee"
        MANAGER = "MANAGER", "Manager"  # gestor: usuário do painel web

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="people")
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=30)

    type = models.CharField(
        max_length=20,
        choices=PersonType.choices,
        db_index=True,
    )

    license_number = models.CharField(max_length=100, null=True, blank=True)   # só driver
    employee_code = models.CharField(max_length=100, null=True, blank=True)    # employee e manager

    def clean(self):
        if self.type == self.PersonType.DRIVER:
            if not self.license_number:
                raise ValidationError({"license_number": "Driver precisa de license_number."})
            if self.employee_code:
                raise ValidationError({"employee_code": "Driver não pode ter employee_code."})

        if self.type == self.PersonType.EMPLOYEE:
            if not self.employee_code:
                raise ValidationError({"employee_code": "Employee precisa de employee_code."})
            if self.license_number:
                raise ValidationError({"license_number": "Employee não pode ter license_number."})

        if self.type == self.PersonType.MANAGER:
            if not self.employee_code:
                raise ValidationError({"employee_code": "Manager precisa de employee_code."})
            if self.license_number:
                raise ValidationError({"license_number": "Manager não pode ter license_number."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_auto_email_local_part(self):
        if self.type in (self.PersonType.EMPLOYEE, self.PersonType.MANAGER):
            raw = self.employee_code
        else:
            raw = self.license_number
        if raw is None:
            return None
        local = re.sub(r"\s+", "", str(raw).strip().lower())
        return local or None

    def get_auto_email(self):
        """
        E-mail padrão: {employee_code|license_number}@{domínio da empresa}.
        Domínio = Company.email_domain ou derivado do nome (ex.: Samsung -> samsung.com).
        """
        local = self.get_auto_email_local_part()
        if not local:
            return None
        domain = self.company.get_email_domain()
        return normalize_email(f"{local}@{domain}")


class AccessAccount(BaseModel):
    person = models.OneToOneField(
        Person,
        on_delete=models.CASCADE,
        related_name="access_account",
    )

    email = models.EmailField(unique=True, db_index=True)

    password_hash = models.CharField(max_length=255)

    must_change_password = models.BooleanField(default=True)

    failed_login_attempts = models.IntegerField(default=0)

    last_login = models.DateTimeField(null=True, blank=True)

    blocked_until = models.DateTimeField(null=True, blank=True)

    # Redefinição de senha por código (OTP) — sem envio por e-mail
    password_reset_code_hash = models.CharField(max_length=255, blank=True)
    password_reset_expires_at = models.DateTimeField(null=True, blank=True)
    password_reset_requested_at = models.DateTimeField(null=True, blank=True)
    password_reset_code_used = models.BooleanField(default=True)

    def clean(self):
        super().clean()
        if self.email:
            self.email = normalize_email(self.email)

    def save(self, *args, **kwargs):
        if self.email:
            self.email = normalize_email(self.email)
        super().save(*args, **kwargs)

    def set_password(self, raw_password):
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password_hash)

    def set_password_reset_code(self, raw_code: str, expires_at):
        self.password_reset_code_hash = make_password(raw_code)
        self.password_reset_expires_at = expires_at
        self.password_reset_requested_at = timezone.now()
        self.password_reset_code_used = False

    def check_password_reset_code(self, raw_code: str) -> bool:
        if (
            self.password_reset_code_used
            or not self.password_reset_code_hash
            or not self.password_reset_expires_at
        ):
            return False
        if timezone.now() > self.password_reset_expires_at:
            return False
        return check_password(raw_code, self.password_reset_code_hash)

    def clear_password_reset(self):
        self.password_reset_code_hash = ""
        self.password_reset_expires_at = None
        self.password_reset_requested_at = None
        self.password_reset_code_used = True

    def __str__(self):
        return self.email


class Route(BaseModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='routes')
    name = models.CharField(max_length=255)
    vehicle = models.ForeignKey(
        "Vehicle",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="routes",
        help_text="Veículo (e motorista) atribuído à rota — usado pelo app do motorista.",
    )

    def __str__(self):
        return self.name


class RouteStop(BaseModel):
    """Parada ordenada na rota (timeline / RouteStopCard)."""

    route = models.ForeignKey(
        Route,
        on_delete=models.CASCADE,
        related_name="stops",
    )
    meeting_point = models.ForeignKey(
        "MeetingPoint",
        on_delete=models.CASCADE,
        related_name="route_stops",
    )
    sequence = models.PositiveSmallIntegerField(
        help_text="0 = primeiro ponto; ordem crescente até o destino.",
    )

    class Meta:
        ordering = ["sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["route", "sequence"],
                name="core_routestop_unique_route_sequence",
            ),
        ]

    def clean(self):
        super().clean()
        if self.meeting_point_id and self.route_id:
            if self.meeting_point.company_id != self.route.company_id:
                raise ValidationError(
                    {"meeting_point": "O ponto de encontro deve ser da mesma empresa da rota."}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.route.name} #{self.sequence} {self.meeting_point.name}"


class Schedule(BaseModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='schedules')
    weekdays = models.JSONField()
    time = models.TimeField()


class Address(BaseModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='addresses',
        null=True,
        blank=True
    )

    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        related_name='addresses',
        null=True,
        blank=True
    )

    street = models.CharField(max_length=100)
    number = models.CharField(max_length=20)
    city = models.CharField(max_length=50)
    state = models.CharField(max_length=50)
    zip_code = models.CharField(max_length=10)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    def __str__(self):
        return f"{self.street}, {self.number} - {self.city}"


class MeetingPoint(BaseModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='meeting_points')
    name = models.CharField(max_length=255)
    address = models.ForeignKey(Address, on_delete=models.CASCADE, related_name='meeting_points')

    def __str__(self):
        return self.name



class RoutePassenger(BaseModel):
    class BoardingStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        ABSENT = "absent", "Absent"

    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        related_name='route_passengers',
        limit_choices_to={'type': 'EMPLOYEE'},
        db_index= True
    )
    route = models.ForeignKey(
        Route,
        on_delete=models.CASCADE,
        related_name='route_passengers',
        db_index= True
    )
    route_stop = models.ForeignKey(
        "RouteStop",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="passengers",
        help_text="Parada de embarque/desembarque; opcional para compatibilidade.",
    )
    boarding_status = models.CharField(
        max_length=20,
        choices=BoardingStatus.choices,
        default=BoardingStatus.PENDING,
        db_index=True,
    )

    class Meta:
        unique_together = ('person', 'route')
        indexes = [
            models.Index(fields=["person", "route"]),
        ]

    def clean(self):
        super().clean()
        if self.route_stop_id and self.route_id:
            if self.route_stop.route_id != self.route_id:
                raise ValidationError(
                    {"route_stop": "A parada deve pertencer à mesma rota."}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

class RouteEvent(BaseModel):
    EVENT_TYPE_CHOICES = [
        ('departure', 'Departure'),
        ('arrival', 'Arrival'),
        ('stop', 'Stop'),
        ('delay', 'Delay'),
        ('incident', 'Incident'),
    ]

    route = models.ForeignKey(
        Route,
        on_delete=models.CASCADE,
        related_name='events'
    )

    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES)
    description = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.route.name} - {self.event_type}"

class Vehicle(BaseModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='vehicles',
        null=True,
        blank=True
    )

    driver = models.ForeignKey(
        Person,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vehicles',
        limit_choices_to={'type': 'DRIVER'},
    )

    plate_number = models.CharField(max_length=20, unique=True)
    model = models.CharField(max_length=100)
    capacity = models.PositiveIntegerField()

    def __str__(self):
        return self.plate_number