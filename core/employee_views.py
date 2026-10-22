from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .employee_serializers import (
    BoardingStatusSerializer,
    EmployeeProfileSerializer,
    EmployeeTripSerializer,
)
from .live import live_status
from .models import RouteEvent, RoutePassenger, RouteStop
from .permissions import IsEmployee


def _employee_trips_queryset(person):
    return (
        RoutePassenger.objects.filter(
            is_active=True, person=person, route__is_active=True
        )
        .select_related(
            "route",
            "route__company",
            "route__vehicle",
            "route__vehicle__driver",
            "route__vehicle__location",
            "route_stop",
        )
        .prefetch_related(
            Prefetch(
                "route__stops",
                queryset=RouteStop.objects.filter(is_active=True)
                .select_related("meeting_point", "meeting_point__address")
                .order_by("sequence"),
            ),
            Prefetch(
                "route__events",
                queryset=RouteEvent.objects.filter(is_active=True).order_by("-timestamp"),
            ),
        )
        .order_by("id")
    )


class EmployeeProfileView(APIView):
    """GET /api/me/ — perfil do colaborador logado."""

    permission_classes = [IsAuthenticated, IsEmployee]

    def get(self, request):
        return Response(EmployeeProfileSerializer().to_representation(request.user.person))


class EmployeeTripsView(APIView):
    """GET /api/me/trips/ — rotas em que o colaborador é passageiro."""

    permission_classes = [IsAuthenticated, IsEmployee]

    def get(self, request):
        ser = EmployeeTripSerializer()
        return Response(
            [ser.to_representation(rp) for rp in _employee_trips_queryset(request.user.person)]
        )


class EmployeeTripDetailView(APIView):
    """GET /api/me/trips/{id}/ — detalhe de uma viagem do colaborador."""

    permission_classes = [IsAuthenticated, IsEmployee]

    def get(self, request, pk):
        rp = get_object_or_404(_employee_trips_queryset(request.user.person), pk=pk)
        return Response(EmployeeTripSerializer().to_representation(rp))


class EmployeeBoardingView(APIView):
    """
    POST /api/me/trips/{id}/boarding/ {"status": "confirmed"|"absent"|"pending"}
    O colaborador confirma presença ou avisa que não vai embarcar.
    """

    permission_classes = [IsAuthenticated, IsEmployee]

    def post(self, request, pk):
        rp = get_object_or_404(_employee_trips_queryset(request.user.person), pk=pk)
        ser = BoardingStatusSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        rp.boarding_status = ser.validated_data["status"]
        rp.save(update_fields=["boarding_status", "updated_at"])
        return Response(
            EmployeeTripSerializer().to_representation(rp), status=status.HTTP_200_OK
        )


class EmployeeTripLiveView(APIView):
    """
    GET /api/me/trips/{id}/live/ — posição da van e previsão de chegada ao ponto.
    Consultado pelo app a cada poucos segundos (limite próprio de requisições).
    """

    permission_classes = [IsAuthenticated, IsEmployee]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "trip_live"

    def get(self, request, pk):
        rp = get_object_or_404(
            RoutePassenger.objects.filter(is_active=True, person=request.user.person, route__is_active=True)
            .select_related("route", "route__company", "route__vehicle", "route__vehicle__location", "route_stop"),
            pk=pk,
        )
        return Response(live_status(rp))
