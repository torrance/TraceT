import datetime
import io
import logging
import json
from typing import Optional

from astropy.coordinates import Angle, AltAz, EarthLocation, SkyCoord
import astropy.time as astrotime
import dateutil.parser
from django.db import models
from django.urls import reverse
from django.utils import timezone
import jsonpath_rfc9535 as jsonpath
from lxml import etree

from . import vote
from .utils import truthy


logger = logging.getLogger(__name__)


class GCNStream(models.Model):
    class Format(models.TextChoices):
        XML = ("xml", "XML")
        JSON = ("json", "JSON")

    name = models.CharField(max_length=500, unique=True)
    type = models.CharField(max_length=500, choices=Format, default="xml")

    def __str__(self):
        return self.name


class Event(models.Model):
    stream = models.ForeignKey(GCNStream, on_delete=models.CASCADE)
    created = models.DateTimeField(default=timezone.now)
    payload = models.BinaryField()
    istest = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created"]
        indexes = [models.Index(fields=["-created"])]

    def __str__(self):
        return str(self.stream)

    def get_absolute_url(self):
        return reverse("event", args=[self.id])

    def file_type(self):
        return self.stream.get_type_display()

    def query(self, path):
        # Handle empty paths gracefully
        if not path:
            return None

        try:
            if self.stream.type == "xml":
                return etree.parse(io.BytesIO(self.payload)).xpath(path)[0]
            elif self.stream.type == "json":
                return jsonpath.find(path, json.loads(self.payload))[0].value
        except IndexError:
            # In the case that no value is found at the path, we return None
            return None

    def pretty_payload(self):
        if self.stream.type == "xml":
            return etree.tostring(
                etree.parse(io.BytesIO(self.payload)), pretty_print=True
            ).decode()
        elif self.stream.type == "json":
            return json.dumps(json.loads(self.payload), indent=4)


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
        help_text="The (x|j)json path to event time. This value is set by the first matching event and is not overridden by subsequent events.",
    )

    objects = Manager()

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("trigger", args=[self.id])

    def get_eventgroup(self, event: Event) -> Optional["EventGroup"]:
        groupid = event.query(self.groupby)
        if groupid is None:
            return None
        return self.eventgroup_set.filter(groupid=groupid).first()

    def get_conditions(self):
        return [*self.numericrangecondition_set.all(), *self.booleancondition_set.all()]


class EventGroup(models.Model):
    class Manager(models.Manager):
        def get_queryset(self):
            return (
                super()
                .get_queryset()
                .prefetch_related("events")
                .select_related("trigger")
            )

    trigger = models.ForeignKey(Trigger, on_delete=models.CASCADE)
    events = models.ManyToManyField(Event)
    groupid = models.CharField(max_length=500)
    time = models.DateTimeField(null=True)

    def __str__(self):
        return f"EventGroup(Trigger={self.trigger.id} GroupID={self.groupid})"

    def pointing(self, attime: Optional[datetime] = None) -> Optional[SkyCoord]:
        events = self.events.order_by("-created")
        if attime:
            events = events.filter(created__lte=attime)

        for event in events:
            ra = event.query(self.trigger.ra_path)
            dec = event.query(self.trigger.dec_path)
            if ra and dec:
                return SkyCoord(ra, dec, unit=("deg", "deg"))
        else:
            return None

    def getpointing(self, event: Event) -> tuple[Optional[SkyCoord], bool]:
        groupid = event.query(self.groupby)
        eventgroup = self.eventgroup(groupid)
        events = eventgroup.priorevents(event)

        pointing = None
        isnew = False
        for i in range(len(events)):
            if self.evaluate(event):
                newpointing = SkyCoord(
                    event.query(self.trigger.ra),
                    event.query(self.trigger.dec),
                    unit=("deg", "deg"),
                )

                if (
                    pointing is None
                    or pointing.separation(newpointing).deg >= self.repointing_threshold
                ):
                    pointing = newpointing
                    isnew = True
                else:
                    isnew = False

        return pointing, isnew

    def evaluateconditions(self, attime: Optional[datetime] = None) -> list[vote.Vote]:
        q = self.events.order_by("created")
        if attime is not None:
            q = q.filter(created__lte=attime)
        events = list(q)

        if len(events) == 0:
            # Require at least one event
            return [vote.Fail("No events")]

        # Initialize evaluations array with oldest event
        event = events.pop(0)
        evaluations = [c.vote(event) for c in self.trigger.get_conditions()]

        # Append all addition evaluations from remaining events
        for event in events:
            for i, c in enumerate(self.trigger.get_conditions()):
                evaluations[i] += c.vote(event)

        return evaluations

    def evaluate(self, attime: Optional[datetime] = None) -> bool:
        # In case of no conditions, set default result as vote.Pass
        # min() expects a minimum of 2 values, so we pass the default twice.
        return bool(
            min(*self.evaluateconditions(attime=attime), vote.Pass(), vote.Pass())
        )


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

    # def get_conditions(self):
    #     return super().get_conditions() + [
    #         MinimumAltitudeCondition(
    #             EarthLocation.from_geodetic(
    #                 lon="116:40:14.93", lat="-26:42:11.95", height=377.8
    #             ),
    #             self.ra,
    #             self.dec,
    #             Angle(self.minimum_altitude, unit="deg"),
    #         )
    #     ]


class Result(models.IntegerChoices):
    PASS = 1
    MAYBE = 0
    FAIL = -1

    @staticmethod
    def asvote(result: int, name: str) -> vote.Vote:
        return {
            1: vote.Pass(name),
            0: vote.Maybe(name),
            -1: vote.Fail(name),
        }[result]


class NumericRangeCondition(models.Model):
    selector = models.CharField(max_length=250)
    val1 = models.FloatField(verbose_name="≥")
    val2 = models.FloatField(verbose_name="＜")
    if_true = models.IntegerField(choices=Result)
    if_false = models.IntegerField(choices=Result)
    trigger = models.ForeignKey(Trigger, on_delete=models.CASCADE)

    def __str__(self):
        return f"IF {self.val1} ≤ {self.selector} < {self.val2} THEN {self.get_if_true_display()} ELSE {self.get_if_false_display()}"

    def vote(self, event: Event) -> vote.Vote:
        try:
            val = event.query(self.selector)
            if val is None:
                return vote.Error(f"No element at path: {self.selector}")

            if self.val1 <= float(val) < self.val2:
                return Result.asvote(self.if_true, str(self))
        except ValueError as e:
            # Unable to convert to float
            raise vote.Error(str(e))

        return Result.asvote(self.if_false, str(self))


class BooleanCondition(models.Model):
    selector = models.CharField(max_length=250)
    if_true = models.IntegerField(choices=Result)
    if_false = models.IntegerField(choices=Result)
    trigger = models.ForeignKey(Trigger, on_delete=models.CASCADE)

    def __str__(self):
        return f"IF {self.selector} THEN {self.get_if_true_display()} ELSE {self.get_if_false_display()}"

    def vote(self, event: Event) -> vote.Vote:
        try:
            val = event.query(self.selector)
            if val is None:
                return vote.Error(f"No element at path: {self.selector}")

            if truthy(val):
                return Result.asvote(self.if_true, str(self))
        except ValueError as e:
            # Unable to convert to boolean
            return vote.Error(str(e))

        return Result.asvote(self.if_false, str(self))


class MinimumAltitudeCondition:
    def __init__(
        self,
        loc: EarthLocation,
        raselector: str,
        decselector: str,
        minimum_altitude: Angle,
    ):
        self.loc = loc
        self.raselector = raselector
        self.decselector = decselector
        self.minimum_altitude = minimum_altitude

    def __str__(self):
        return f"altitude > {self.minimum_altitude} [deg]"

    def vote(self, events: list[Event]) -> vote.Vote:
        for event in reversed(events):
            ra = event.query(self.raselector)
            dec = event.query(self.decselector)

            if ra and dec:
                skycoord = SkyCoord(ra, dec, unit=("deg", "deg"))
                break
        else:
            return vote.Error("No valid RaDec")

        altaz = AltAz(
            location=self.loc,
            obstime=astrotime.Time(events[-1].created),  # use time of most recent event
        )

        altitude = skycoord.transform_to(altaz).alt

        if altitude >= self.minimum_altitude:
            return vote.Pass(str(self))
        else:
            return vote.Fail(str(self))
