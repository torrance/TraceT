import contextvars
import datetime
import logging
from typing import Optional

from astropy.coordinates import SkyCoord

from django.db import models
from django.core import mail
from django.urls import reverse

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
    active = models.BooleanField(
        default=False,
        help_text="Is this trigger active? Set to inactive during testing to avoid sending spurious triggers to observatories.",
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
        "now", default=datetime.datetime.max
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
        notices = self.notices.order_by("-created").filter(
            created__lte=Event.now.get()
        )
        if not Event.testing.get():
            notices = notices.filter(istest=False)

        return list(notices)

    def pointing(self) -> Optional[SkyCoord]:
        for notice in self.get_notices():
            ra = notice.query(self.trigger.ra_path)
            dec = notice.query(self.trigger.dec_path)
            if ra and dec:
                return SkyCoord(ra, dec, unit=("deg", "deg"))
        else:
            return None

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
            notice = self.get_notices().pop()

            mail.send_mail(
                "Event triggered!",
                f"Trigger (id={self.trigger.id}) has been activated by Notice (id={notice.id}).",
                "admin@tracet.duckdns.org",
                ["torrance123@gmail.com"],
                fail_silently=True,
            )

            logger.warning(
                f"Trigger (id={self.trigger.id}) has been activated by Notice (id={notice.id})."
            )
