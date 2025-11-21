from django.contrib import admin

# Register your models here.
from . import models

@admin.register(models.GCNStream)
class GCNStream(admin.ModelAdmin):
    list_display = ["name", "type"]


@admin.register(models.Notice)
class Notice(admin.ModelAdmin):
    list_display = ["stream", "file_type", "created"]
    readonly_fields = ["stream", "created", "pretty_payload"]
    exclude = ["payload"]

class NumericRangeCondition(admin.TabularInline):
    model = models.NumericRangeCondition
    extra = 0
    can_move = True


class BooleanCondition(admin.TabularInline):
    model = models.BooleanCondition
    extra = 0
    can_move = True

class ContainsCondition(admin.TabularInline):
    model = models.ContainsCondition
    extra = 0
    can_move = True

class MWA(admin.StackedInline):
    model = models.MWA

@admin.register(models.Trigger)
class Trigger(admin.ModelAdmin):
    inlines = [NumericRangeCondition, BooleanCondition, ContainsCondition, MWA]