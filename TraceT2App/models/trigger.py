import contextvars
import datetime
import logging
from typing import Optional
from warnings import deprecated

from astropy.coordinates import SkyCoord

from django.db import models
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from TraceT2App.models import GCNStream, Notice
import TraceT2App.vote as vote


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
        return reverse("trigger", args=[self.id])

    def get_event(self, notice: Notice) -> Optional["Event"]:
        groupid = notice.query(self.groupby)
        if groupid is None:
            return None
        return self.event_set.filter(groupid=groupid).first()

    def get_conditions(self):
        return [
            *self.numericrangecondition_set.all(),
            *self.booleancondition_set.all(),
            *self.containscondition_set.all(),
        ]

    def get_telescopes(self):
        return [self.mwa, self.atca]


class Event(models.Model):
    class Manager(models.Manager):
        def get_queryset(self):
            return (
                super()
                .get_queryset()
                .prefetch_related("notices")
                .select_related("trigger")
            )

    # Context variables
    # In debugging, we want to evaluate the Event as if it were run in the past
    now: contextvars.ContextVar[datetime.datetime] = contextvars.ContextVar(
        "now", default=datetime.datetime.max.replace(tzinfo=datetime.UTC)
    )
    # Are we currently testing?
    testing = contextvars.ContextVar("testing", default=False)

    trigger = models.ForeignKey(Trigger, on_delete=models.CASCADE)
    notices = models.ManyToManyField(Notice)
    groupid = models.CharField(max_length=500)
    time = models.DateTimeField(null=True)

    def __str__(self):
        return f"Event(Trigger={self.trigger.id} GroupID={self.groupid})"

    def get_notices(self, ignoretest: bool = True) -> list[Notice]:
        notices = self.notices.order_by("created").filter(created__lte=Event.now.get())
        if not Event.testing.get():
            notices = notices.filter(istest=False)

        return list(notices)

    def querylatest(self, query):
        for notice in self.get_notices():
            result = notice.query(query)
            if result is not None:
                return result

        return None

    @deprecated("RA/Dec queries are to be moved to the Telescope object")
    def pointing(self) -> Optional[SkyCoord]:
        for notice in self.get_notices():
            ra = notice.query(self.trigger.ra_path)
            dec = notice.query(self.trigger.dec_path)
            if ra and dec:
                return SkyCoord(ra, dec, unit=("deg", "deg"))
        else:
            return None

    @deprecated("RA/Dec queries are to be moved to the Telescope object")
    def getpointing(self) -> tuple[Optional[SkyCoord], bool]:
        pointing = None
        isnew = False
        for tmax in [n.created for n in self.get_notices()]:
            with Event.now.set(tmax):
                isnew = False
                if self.evaluate():
                    newpointing = self.pointing()

                    if newpointing is None:
                        continue

                    if (
                        pointing is None
                        or pointing.separation(newpointing).deg
                        > self.repointing_threshold()
                    ):
                        pointing = newpointing
                        isnew = True

        return pointing, isnew

    def evaluateconditions(self) -> list[vote.Vote]:
        notices = self.get_notices()

        if len(notices) == 0:
            # Require at least one event
            return [vote.Fail("No notices")]

        # Initialize evaluations array with oldest notice
        notice = notices.pop(0)
        evaluations = [c.vote(notice) for c in self.trigger.get_conditions()]

        # Append all addition evaluations from remaining notices
        for notice in notices:
            for i, c in enumerate(self.trigger.get_conditions()):
                evaluations[i] += c.vote(notice)

        return evaluations

    def evaluate(self) -> bool:
        # In case of no conditions, set default result as vote.Pass
        # min() expects a minimum of 2 values, so we pass the default twice.
        return bool(
            min(
                *self.evaluateconditions(),
                vote.Pass(),
                vote.Pass(),
            )
        )

    def runtrigger(self):
        if self.evaluate():
            for telescope in self.trigger.get_telescopes():
                observation = (
                    Observation.objects.filter(
                        success=True,
                        istest=False,
                        observatory=telescope.OBSERVATORY,
                        finish__gte=timezone.now(),
                    )
                    .order_by("-finish")
                    .first()
                )

                if observation is None or observation.priority < self.trigger.priority:
                    if observation := telescope.schedulenow(self):
                        return observation

                # TODO
                # Schedulenow only if:
                # 1. Existing observation is owned by us
                # 2. Pointing direction is substantially updated.

        return False

class Observation(models.Model):
    trigger = models.ForeignKey(Trigger, null=True, on_delete=models.SET_NULL)
    event = models.ForeignKey(Event, null=True, on_delete=models.SET_NULL)
    start = models.DateTimeField(default=timezone.now)
    finish = models.DateTimeField()
    observatory = models.CharField(max_length=500)
    priority = models.IntegerField()
    success = models.BooleanField()
    istest = models.BooleanField()
    log = models.TextField()

    def __bool__(self):
        return self.success and not self.istest
