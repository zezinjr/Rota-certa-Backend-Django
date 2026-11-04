# A maior parte das views da API fica em viewsets.py, auth_views.py e employee_views.py.
from django.db import connection
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import push, whatsapp


class HealthView(APIView):
    """
    GET /api/health/ — sem login. Usado pelo deploy automático (e por monitores de uptime)
    para saber se a API subiu e fala com o banco. 503 se o banco não responder.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception:  # qualquer falha do banco vira 503
            return Response({"status": "error", "database": False}, status=503)
        return Response({
            "status": "ok",
            "database": True,
            "push": push.is_enabled(),
            "whatsapp": whatsapp.is_enabled(),
        })
