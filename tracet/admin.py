from django.db import connection
from django.contrib import admin

# Register your models here.
from . import models


@admin.register(models.GCNStream)
class GCNStream(admin.ModelAdmin):
    list_display = ["topic", "type", "notice_count", "payload_filesize", "status"]

    @admin.display(description="Payload size [MB]")
    def payload_filesize(self, obj):
        # Return the cumulative payload filesize of this topic's associated notices. [MB]
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT SUM(OCTET_LENGTH(payload)) FROM tracet_notice WHERE stream_id = %s",
                [obj.id],
            )
            return cursor.fetchone()[0] / 1e6

    @admin.display(description="Notice count")
    def notice_count(self, obj):
        return obj.notices.count()

    def has_change_permission(self, request, obj=None):
        return False  # Disable editing existing entries
