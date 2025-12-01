import datetime
import logging
from typing import Optional

from django.db import models
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils import timezone

from TraceT2App.models import Notice
from TraceT2App.models import Trigger, Event
from TraceT2App.utils import truthy


logger = logging.getLogger(__name__)


class Vote(models.IntegerChoices):
    FAIL = -1, "Fail"
    MAYBE = 0, "Maybe"
    PASS = 1, "Pass"


class Decision(models.Model):
    class Manager(models.Manager):
        def get_queryset(self):
            return (
                super()
                .get_queryset()
                .prefetch_related("factors")
                .select_related("event")
            )

    objects = Manager()

    event = models.ForeignKey(Event, related_name="decisions", on_delete=models.CASCADE)
    created = models.DateTimeField(default=timezone.now)
    simulated = models.BooleanField()

    def save(self, *args, **kwargs):
        res = super().save(*args, **kwargs)

        self.factors.all().delete()

        # Attach all factors
        notices = self.event.notices.filter(created__lte=self.created).order_by(
            "created"
        )
        if not self.simulated:
            notices.filter(istest=False)

        notices = list(notices)

        if len(notices) == 0:
            factors = [Factor(condition="Event contains no notices", vote=Vote.FAIL)]
        else:
            # Initialize factors list with oldest notice
            notice = notices.pop(0)
            factors = [c.vote(notice) for c in self.event.trigger.get_conditions()]

            # Append all additional factors from remaining notices
            for notice in notices:
                for i, c in enumerate(self.event.trigger.get_conditions()):
                    # The following + is doing a lot!
                    #   - Indeterminate votes (== None) will inherit most recent non-null Factor
                    #   - Otherwise, we give precedence to the most recent Factor
                    factors[i] += c.vote(notice)

        self.factors.add(*factors, bulk=False)

        return res

    @property
    def conclusion(self) -> int:
        return max(
            *[factor.vote for factor in self.factors.all()], Vote.PASS, Vote.PASS
        )


class Factor(models.Model):
    decision = models.ForeignKey(
        Decision, related_name="factors", on_delete=models.CASCADE
    )

    condition = models.TextField()
    vote = models.IntegerField(null=True, blank=True, choices=Vote)
    inherited = models.BooleanField(default=False)

    def __add__(self, other: Factor) -> Factor:
        # Note that this operation is not commutative: order matters!
        if other.vote is None:
            return Factor(condition=self.condition, vote=self.vote, inherited=True)
        else:
            return Factor(condition=other.condition, vote=other.vote)

    def get_vote_display(self):
        if self.vote is None:
            return "Error"
        else:
            return Vote(self.vote).label

    def html(self):
        return mark_safe(
            f'<span class="vote {self.get_vote_display().lower()} {"inherited" if self.inherited else ""}" title="{escape(self.condition)}"></span>'
        )


class NumericRangeCondition(models.Model):
    selector = models.CharField(max_length=250)
    val1 = models.FloatField(verbose_name="≥")
    val2 = models.FloatField(verbose_name="＜")
    if_true = models.IntegerField(choices=Vote)
    if_false = models.IntegerField(choices=Vote)
    trigger = models.ForeignKey(Trigger, on_delete=models.CASCADE)

    def __str__(self):
        return f"IF {self.val1} ≤ {self.selector} < {self.val2} THEN {self.get_if_true_display()} ELSE {self.get_if_false_display()}"

    def vote(self, notice: Notice) -> Factor:
        try:
            val = notice.query(self.selector)
            if val is None:
                return Factor(condition=str(self))

            if self.val1 <= float(val) < self.val2:
                return Factor(condition=str(self), vote=self.if_true)
        except ValueError as e:
            # Unable to convert to float
            return Factor(condition=str(self))

        return Factor(condition=str(self), vote=self.if_false)


class BooleanCondition(models.Model):
    selector = models.CharField(max_length=250)
    if_true = models.IntegerField(choices=Vote)
    if_false = models.IntegerField(choices=Vote)
    trigger = models.ForeignKey(Trigger, on_delete=models.CASCADE)

    def __str__(self):
        return f"IF {self.selector} THEN {self.get_if_true_display()} ELSE {self.get_if_false_display()}"

    def vote(self, notice: Notice) -> vote.Vote:
        try:
            val = notice.query(self.selector)
            if val is None:
                return Factor(condition=str(self))

            if truthy(val):
                return Factor(condition=str(self), vote=self.if_true)
        except ValueError as e:
            # Unable to convert to boolean
            return Factor(condition=str)

        return Factor(condition=str(self), vote=self.if_false)


class ContainsCondition(models.Model):
    selector = models.CharField(max_length=250)
    vals = models.TextField()
    if_true = models.IntegerField(choices=Vote)
    if_false = models.IntegerField(choices=Vote)
    trigger = models.ForeignKey(Trigger, on_delete=models.CASCADE)

    def __str__(self):
        vals = self.get_vals()
        if len(vals) <= 4:
            return f"IF {self.selector} IN {tuple(vals)})"
        else:
            return f"IF {self.selector} IN ('{vals[0]}', '{vals[1]}', ..., '{vals[-2]}', '{vals[-1]}')"

    def get_vals(self):
        return [line.strip() for line in self.vals.strip().splitlines()]

    def vote(self, notice: Notice) -> vote.Vote:
        try:
            val = notice.query(self.selector)
            if val is None:
                return Factor(condition=str(self))

            val = str(val)
            if val in self.get_vals():
                return Factor(condition=str(self), vote=self.if_true)
        except ValueError as e:
            # Unable to convert to string
            return Factor(condition=str(self))

        return Factor(condition=str(self), vote=self.if_false)
