from nested_admin import NestedTabularInline, NestedModelAdmin, NestedStackedInline

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


class NumericRangeCondition(NestedTabularInline):
    model = models.NumericRangeCondition
    extra = 0
    can_move = True


class BooleanCondition(NestedTabularInline):
    model = models.BooleanCondition
    extra = 0
    can_move = True


class ContainsCondition(NestedTabularInline):
    model = models.ContainsCondition
    extra = 0
    can_move = True


class MWACorrelator(NestedStackedInline):
    model = models.MWACorrelator


class ATCABand(NestedTabularInline):
    model = models.telescopes.ATCABand
    extra = 1
    can_move = False


class ATCA(NestedStackedInline):
    model = models.ATCA
    inlines = [ATCABand]


@admin.register(models.Observation)
class Observation(admin.ModelAdmin):
    pass


@admin.register(models.Trigger)
class Trigger(NestedModelAdmin):
    inlines = [NumericRangeCondition, BooleanCondition, ContainsCondition, MWACorrelator, ATCA]
