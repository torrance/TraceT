from nested_admin import NestedTabularInline, NestedModelAdmin, NestedStackedInline

from django.contrib import admin

# Register your models here.
from . import models


@admin.register(models.GCNStream)
class GCNStream(admin.ModelAdmin):
    list_display = ["topic", "type", "status"]
    readonly_fields = ["status"]