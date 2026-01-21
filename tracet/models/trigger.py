import datetime
import logging
from typing import Optional
from warnings import deprecated

from astropy.coordinates import SkyCoord
import dateutil

from django.db import models
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from tracet.models.conditions import Decision
from tracet.models.telescopes import Observation, Telescope

logger = logging.getLogger(__name__)


class Trigger(models.Model):
    class Manager(models.Manager):
        def get_queryset(self):
            return (
                super()
                .get_queryset()
                .prefetch_related("numericrangeconditions", "booleanconditions")
            )

    name = models.CharField(max_length=250)
    user = models.ForeignKey(
        get_user_model(), related_name="triggers", on_delete=models.CASCADE
    )
    created = models.DateField(default=timezone.now)
    priority = models.IntegerField(default=0)
    active = models.BooleanField(
        default=False,
        help_text="Inactive triggers will send observation requests to observatories marked as testing only.",
    )
    streams = models.ManyToManyField("GCNStream")
    groupby = models.CharField(max_length=500)
    time_path = models.CharField(
        max_length=250,
        help_text="The (x|j)json path to event time. This value is set by the first matching notice and is not overridden by subsequent notices.",
    )
    expiry = models.FloatField(
        help_text="Events will expire once this duration has elapsed since first notice. Subsequent notices will not trigger automated observations; manual retriggers will ignore this condition. [minute]",
    )

    objects = Manager()

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("triggerview", args=[self.id])

    def get_or_create_event(self, notice: "Notice") -> Optional["Event"]:
        # Check if we are listening to this particular stream
        if not self.streams.filter(id=notice.stream.id).exists():
            return None

        # Extract the group id (or return None if we can't find it)
        groupid = notice.query(self.groupby)
        if groupid is None:
            logger.warning(
                f"Processing Notice (id={notice.id}) for Trigger (id={self.id}) but unable to query groupid"
            )
            return None

        # Get or create event and ensure notice is addded
        event, _ = self.events.get_or_create(groupid=groupid)
        event.notices.add(notice)

        return event

    def get_conditions(self):
        return [
            *self.numericrangeconditions.all(),
            *self.booleanconditions.all(),
            *self.equalityconditions.all(),
        ]

    def get_telescope(self):
        try:
            return [
                getattr(self, attr)
                for attr in dir(self)
                if hasattr(self, attr) and issubclass(type(getattr(self, attr)), Telescope)
            ][0]
        except IndexError:
            return None

    def get_last_attempted_observation(self):
        return (
            Observation.objects.filter(decision__event__trigger__id=self.id)
            .order_by("-created")
            .first()
        )

    def get_recent_events(self, n=5):
        return self.events.order_by("-time")[:5]


class Event(models.Model):
    class Manager(models.Manager):
        def get_queryset(self):
            return (
                super()
                .get_queryset()
                .prefetch_related("notices")
                .select_related("trigger")
            )

    class Meta:
        ordering = ["-time"]
        indexes = [models.Index(fields=["-time"]), models.Index(fields=["groupid"])]

    objects = Manager()

    trigger = models.ForeignKey(
        "Trigger", related_name="events", on_delete=models.CASCADE
    )
    notices = models.ManyToManyField("Notice")
    groupid = models.CharField(max_length=500)
    time = models.DateTimeField(null=True)

    def __str__(self):
        return f"Event(Trigger={self.trigger.id} GroupID={self.groupid})"

    def get_absolute_url(self):
        return self.trigger.get_absolute_url() + "#eventid-" + self.groupid

    def querylatest(self, query):
        for notice in self.notices.order_by("-created"):
            result = notice.query(query)
            if result is not None:
                return result

        return None

    def updatetime(self):
        self.time = None
        time_path = self.trigger.time_path

        for notice in self.notices.all():
            # Update event time to match the youngest time present in notices
            try:
                t = dateutil.parser.parse(
                    notice.query(time_path),
                    default=datetime.datetime(1900, 1, 1, tzinfo=datetime.UTC),
                )

                if self.time is None or (t and t < self.time):
                    self.time = t
                    self.save()
            except (TypeError, dateutil.parser.ParserError) as e:
                logger.warning(
                    f"Failed to parse time (Trigger id={self.trigger.id}, Notice id={notice.id}) with path {self.trigger.time_path}. Error: {str(e)}"
                )

        self.save()

    def get_last_interesting_decision(self) -> Optional["Decision"]:
        """
        This method is used in providing front page summary of each event.

        In order of precedence:
        1. Return the most recent decision that triggered a successful observation
        2. Return the most recent decision that triggered an unsuccessful observation
        3. Return most recent decision
        """
        observation = (
            Observation.objects.exclude(decision__source=Decision.Source.SIMULATED)
            .filter(decision__event__id=self.id, status=Observation.Status.API_OK)
            .order_by("-created")
            .first()
        )

        if observation is not None:
            return observation.decision

        observation = (
            Observation.objects.exclude(decision__source=Decision.Source.SIMULATED)
            .filter(decision__event__id=self.id)
            .order_by("-created")
            .first()
        )

        if observation is not None:
            return observation.decision

        return (
            self.decisions.exclude(source=Decision.Source.SIMULATED)
            .order_by("-created")
            .first()
        )
