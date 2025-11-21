import logging

from django.db import models

from TraceT2App.models import Trigger


logger = logging.getLogger(__name__)


class Telescope(models.Model):
    class Meta:
        abstract = True

    trigger = models.OneToOneField(
        Trigger, related_name="%(class)s", on_delete=models.CASCADE
    )

    projectid = models.CharField(max_length=500)
    repointing_threshold = models.FloatField()
    frequency = models.CharField(max_length=500)
    frequency_resolution = models.FloatField()
    time_resolution = models.FloatField()
    minimum_altitude = models.FloatField()
    maximum_window = models.IntegerField(
        help_text=(
            "The maximum window of time following an event in which observations maybe be "
            "scheduled. Observations will may be truncated to not exceed this window, and "
            "events occurring after this window will be ignored. [second]"
        )
    )


class MWA(Telescope):
    def __str__(self):
        return "MWA Configuration"
