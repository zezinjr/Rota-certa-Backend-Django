import time
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.live import bearing_deg, cumulative_distances, route_path, save_vehicle_location
from core.models import AccessAccount, Route, RouteEvent


class Command(BaseCommand):
    help = (
        "Faz a van de uma rota 'andar' pelas paradas até a empresa, gravando a posição "
        "a cada poucos segundos (como o app do motorista faria). Use para testar o "
        "acompanhamento ao vivo no app do colaborador. Ctrl+C para parar."
    )

    def add_arguments(self, parser):
        target = parser.add_mutually_exclusive_group(required=True)
        target.add_argument("--route-id", type=int, help="ID da rota.")
        target.add_argument("--email", help="E-mail do colaborador: simula a rota dele.")
        parser.add_argument("--minutos", type=float, default=5.0,
                            help="Duração aproximada do trajeto inteiro (padrão: 5 min, bom para demonstração).")
        parser.add_argument("--speed-kmh", type=float, default=None,
                            help="Velocidade fixa da van em km/h (ignora --minutos). Ex.: 30 = ritmo real.")
        parser.add_argument("--interval", type=float, default=3.0, help="Segundos entre posições (padrão: 3).")
        parser.add_argument("--stop-seconds", type=float, default=10.0, help="Tempo parado em cada parada (padrão: 10).")
        parser.add_argument("--start-meters", type=float, default=0.0,
                            help="Começar já tantos metros adiante no trajeto.")
        parser.add_argument("--loop", action="store_true", help="Recomeçar do início ao chegar.")
        parser.add_argument("--no-events", action="store_true", help="Não registrar eventos de saída/chegada.")

    def handle(self, *args, **opts):
        route = self.resolve_route(opts)
        if route.vehicle is None:
            raise CommandError(f"A rota '{route.name}' não tem veículo.")
        path = route_path(route)
        if len(path) < 2:
            raise CommandError("A rota precisa de pelo menos 2 pontos (paradas/empresa) com coordenadas.")

        cum = cumulative_distances(path)
        source = "pelas ruas" if any(p.stop is None for p in path[:-1]) else "em linha reta (sem trajeto do Google)"
        if opts["speed_kmh"]:
            speed = max(opts["speed_kmh"], 1) / 3.6
        else:
            stops_time = opts["stop_seconds"] * sum(1 for p in path if p.stop is not None)
            speed = cum[-1] / max(opts["minutos"] * 60 - stops_time, 30)
        step = speed * opts["interval"]
        self.stdout.write(self.style.SUCCESS(
            f"Simulando '{route.name}' ({route.vehicle.plate_number}) {source}: {len(path)} pontos, "
            f"{cum[-1] / 1000:.1f} km a {speed * 3.6:.0f} km/h. Ctrl+C para parar."
        ))
        try:
            while True:
                self.run_once(route, path, cum, step, opts)
                if not opts["loop"]:
                    break
        except KeyboardInterrupt:
            self.stdout.write("\nSimulação interrompida.")

    def resolve_route(self, opts):
        if opts["route_id"]:
            route = Route.objects.filter(pk=opts["route_id"]).select_related("vehicle").first()
            if route is None:
                raise CommandError(f"Rota {opts['route_id']} não encontrada.")
            return route
        account = AccessAccount.objects.filter(email=opts["email"].strip().lower()).select_related("person").first()
        if account is None:
            raise CommandError(f"Conta {opts['email']} não encontrada.")
        rp = account.person.route_passengers.filter(is_active=True).select_related("route__vehicle").first()
        if rp is None:
            raise CommandError(f"{opts['email']} não é passageiro de nenhuma rota.")
        return rp.route

    def run_once(self, route, path, cum, step, opts):
        if not opts["no_events"]:
            self.event(route, "departure", "Simulação: saída da garagem", path[0])
        along = max(0.0, min(opts["start_meters"], cum[-1]))
        # Pontos onde a van "chega": paradas e o fim do trajeto (os demais são curvas das ruas).
        checkpoints = [j for j, p in enumerate(path) if p.stop is not None or j == len(path) - 1]
        checkpoints = [j for j in checkpoints if cum[j] >= along]
        while True:
            lat, lng, seg = self.point_at(path, cum, along)
            heading = bearing_deg((path[seg].lat, path[seg].lng), (path[seg + 1].lat, path[seg + 1].lng))
            save_vehicle_location(route.vehicle, route, Decimal(str(lat)), Decimal(str(lng)),
                                  heading=heading, speed=step / opts["interval"], recorded_at=timezone.now())
            while checkpoints and along >= cum[checkpoints[0]]:
                point = path[checkpoints.pop(0)]
                label = point.stop.meeting_point.name if point.stop else "empresa"
                self.stdout.write(f"  [{timezone.localtime():%H:%M:%S}] chegou em {label}")
                if point.stop is not None and opts["stop_seconds"] > 0:
                    time.sleep(opts["stop_seconds"])
            if along >= cum[-1]:
                break
            time.sleep(opts["interval"])
            along = min(along + step, cum[-1])
        if not opts["no_events"]:
            self.event(route, "arrival", "Simulação: chegada na empresa", path[-1])
        self.stdout.write(self.style.SUCCESS("Fim do trajeto."))

    @staticmethod
    def point_at(path, cum, along):
        for i in range(len(path) - 1):
            if along <= cum[i + 1] or i == len(path) - 2:
                length = cum[i + 1] - cum[i]
                t = 0.0 if length == 0 else (along - cum[i]) / length
                t = max(0.0, min(1.0, t))
                return path[i].lat + (path[i + 1].lat - path[i].lat) * t, path[i].lng + (path[i + 1].lng - path[i].lng) * t, i
        return path[-1].lat, path[-1].lng, len(path) - 2

    @staticmethod
    def event(route, event_type, description, point):
        RouteEvent.objects.create(
            route=route, event_type=event_type, description=description,
            latitude=Decimal(f"{point.lat:.6f}"), longitude=Decimal(f"{point.lng:.6f}"),
        )
