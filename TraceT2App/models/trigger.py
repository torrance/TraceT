import datetime
import logging
from typing import Optional
from warnings import deprecated

from astropy.coordinates import SkyCoord
import dateutil

from django.db import models
from django.core import mail
from django.urls import reverse
from django.utils import timezone

import TraceT2App.models
from TraceT2App.models import GCNStream, Notice


logger = logging.getLogger(__name__)


class Trigger(models.Model):
    class Manager(models.Manager):
        def get_queryset(self):
            return (
                super()
                .get_queryset()
                .prefetch_related("numericrangecondition_set", "booleancondition_set")
            )

    name = models.CharField(max_length=250)
    priority = models.IntegerField(default=0)
    active = models.BooleanField(
        default=False,
        help_text="Inactive triggers will send observation requests to observatories marked as testing only.",
    )
    streams = models.ManyToManyField(GCNStream)
    groupby = models.CharField(max_length=500)
    ra_path = models.CharField(max_length=500)
    dec_path = models.CharField(max_length=500)
    time_path = models.CharField(
        max_length=250,
        help_text="The (x|j)json path to event time. This value is set by the first matching notice and is not overridden by subsequent notices.",
    )

    objects = Manager()

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("triggerview", args=[self.id])

    def get_or_create_event(self, notice: Notice) -> Optional["Event"]:
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
        event, _ = self.event_set.get_or_create(groupid=groupid)
        event.notices.add(notice)

        return event

    def get_conditions(self):
        return [
            *self.numericrangecondition_set.all(),
            *self.booleancondition_set.all(),
            *self.containscondition_set.all(),
        ]

    def get_telescopes(self):
        return [getattr(self, t) for t in ("mwa", "atca") if hasattr(self, t)]


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

    trigger = models.ForeignKey(Trigger, on_delete=models.CASCADE)
    notices = models.ManyToManyField(Notice)
    groupid = models.CharField(max_length=500)
    time = models.DateTimeField(null=True)

    def __str__(self):
        return f"Event(Trigger={self.trigger.id} GroupID={self.groupid})"

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
            except dateutil.parser.ParserError as e:
                logger.warning(
                    f"Failed to parse time (Trigger id={self.trigger.id}, Notice id={notice.id}) with path {self.trigger.time_path}. Error: {str(e)}"
                )

        self.save()

    def runtrigger(self):
        decision = TraceT2App.models.Decision.objects.create(
            event=self, simulated=False
        )

        if decision.conclusion == TraceT2App.models.Vote.PASS:
            for telescope in self.trigger.get_telescopes():
                telescope.schedulenow(self)

    # def runtrigger(self):
    #     if self.evaluate():
    #         for telescope in self.trigger.get_telescopes():
    #             observation = (
    #                 Observation.objects.filter(
    #                     success=True,
    #                     istest=False,
    #                     observatory=telescope.OBSERVATORY,
    #                     finish__gte=timezone.now(),
    #                 )
    #                 .order_by("-finish")
    #                 .first()
    #             )

    #             if observation is None or observation.priority < self.trigger.priority:
    #                 if observation := telescope.schedulenow(self):
    #                     return observation

    #             # TODO
    #             # Schedulenow only if:
    #             # 1. Existing observation is owned by us
    #             # 2. Pointing direction is substantially updated.

    #     return False
