from django.contrib import admin

from .models import Notification, PushDevice


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "kind", "channel", "status", "route_passenger", "recipient")
    list_filter = ("channel", "kind", "status", "service_date")
    search_fields = ("route_passenger__person__name", "recipient", "error")
    readonly_fields = [f.name for f in Notification._meta.fields]


@admin.register(PushDevice)
class PushDeviceAdmin(admin.ModelAdmin):
    list_display = ("person", "platform", "is_active", "last_seen_at", "created_at")
    list_filter = ("platform", "is_active")
    search_fields = ("person__name", "token")
    raw_id_fields = ("person",)
