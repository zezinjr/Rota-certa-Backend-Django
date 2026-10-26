from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import (
    AccessAccount,
    Address,
    Company,
    MeetingPoint,
    Person,
    Route,
    RoutePassenger,
    RouteStop,
    Vehicle,
)


def parse_point(text):
    """'-3.0956, -60.0343' (formato copiado do Google Maps) → (Decimal, Decimal)."""
    try:
        lat, lng = (Decimal(part.strip()) for part in text.split(","))
    except (ValueError, InvalidOperation) as exc:
        raise CommandError(f"Coordenada inválida: '{text}'. Use 'latitude, longitude'.") from exc
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise CommandError(f"Coordenada fora do intervalo: '{text}'.")
    return lat.quantize(Decimal("0.000001")), lng.quantize(Decimal("0.000001"))


class Command(BaseCommand):
    help = (
        "Cria uma rota de teste com paradas nas coordenadas informadas (ex.: no trajeto que "
        "um motorista real vai fazer), usando o veículo do motorista e incluindo o colaborador "
        "como passageiro. Pegue as coordenadas no Google Maps (toque longo no mapa)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--motorista", required=True, help="E-mail da conta do motorista (DRIVER).")
        parser.add_argument("--colaborador", required=True, help="E-mail da conta do colaborador (EMPLOYEE).")
        parser.add_argument("--pontos", required=True,
                            help='Paradas em ordem, separadas por ";". Ex.: "-3.0956, -60.0343; -3.0609, -60.0259"')
        parser.add_argument("--ponto-colaborador", type=int, default=None,
                            help="Número da parada do colaborador (1 = primeira). Padrão: a segunda.")
        parser.add_argument("--destino", default=None,
                            help="Coordenada do destino final. Sem ele, o destino é o endereço da empresa do motorista.")
        parser.add_argument("--nome", default="Rota de teste", help="Nome da rota.")
        parser.add_argument("--exclusivo", action="store_true",
                            help="Desativa as outras viagens do colaborador, para o app mostrar só esta.")

    @transaction.atomic
    def handle(self, *args, **opts):
        driver = self.person(opts["motorista"], Person.PersonType.DRIVER)
        employee = self.person(opts["colaborador"], Person.PersonType.EMPLOYEE)
        vehicle = Vehicle.objects.filter(driver=driver, is_active=True).first()
        if vehicle is None:
            raise CommandError(f"O motorista {driver.name} não tem veículo ativo. Vincule um veículo pelo painel.")

        points = [parse_point(p) for p in opts["pontos"].split(";") if p.strip()]
        if len(points) < 2:
            raise CommandError("Informe pelo menos 2 paradas em --pontos.")
        my_stop = opts["ponto_colaborador"] or 2
        if not 1 <= my_stop <= len(points):
            raise CommandError(f"--ponto-colaborador deve estar entre 1 e {len(points)}.")

        company = driver.company
        if opts["destino"]:
            # Empresa própria do teste, para o destino ser exatamente o informado.
            lat, lng = parse_point(opts["destino"])
            company = Company.objects.create(name=opts["nome"], email_domain="rotateste.local")
            Address.objects.create(company=company, street="Destino do teste", number="s/n", city="-",
                                   state="-", zip_code="-", latitude=lat, longitude=lng)

        route = Route.objects.create(company=company, name=opts["nome"], vehicle=vehicle)
        stops = []
        for index, (lat, lng) in enumerate(points):
            address = Address.objects.create(company=company, street=f"Parada {index + 1}", number="s/n",
                                             city="-", state="-", zip_code="-", latitude=lat, longitude=lng)
            point = MeetingPoint.objects.create(company=company, name=f"{opts['nome']} · parada {index + 1}",
                                                address=address)
            stops.append(RouteStop.objects.create(route=route, meeting_point=point, sequence=index))

        if opts["exclusivo"]:
            RoutePassenger.objects.filter(person=employee, is_active=True).update(is_active=False)
        RoutePassenger.objects.create(person=employee, route=route, route_stop=stops[my_stop - 1])

        self.stdout.write(self.style.SUCCESS(f"Rota criada: #{route.id} '{route.name}' com {len(stops)} paradas."))
        self.stdout.write(f"  Motorista: {driver.name} ({opts['motorista']}) · veículo {vehicle.plate_number}")
        self.stdout.write(f"  Colaborador: {employee.name} ({opts['colaborador']}) · embarca na parada {my_stop}")
        if not opts["exclusivo"]:
            self.stdout.write("  Dica: o colaborador tem outras viagens; no app, escolha esta rota no topo da tela Viagem "
                              "(ou rode de novo com --exclusivo).")

    @staticmethod
    def person(email, person_type):
        account = AccessAccount.objects.filter(email=email.strip().lower()).select_related("person").first()
        if account is None:
            raise CommandError(f"Conta {email} não encontrada.")
        if account.person.type != person_type:
            raise CommandError(f"{email} não é do tipo {person_type}.")
        return account.person
