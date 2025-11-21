import logging

from django.db import models

from TraceT2App.models import Notice
from TraceT2App.models import Trigger
from TraceT2App.utils import truthy
import TraceT2App.vote as vote


logger = logging.getLogger(__name__)


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

    def vote(self, notice: Notice) -> vote.Vote:
        try:
            val = notice.query(self.selector)
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

    def vote(self, notice: Notice) -> vote.Vote:
        try:
            val = notice.query(self.selector)
            if val is None:
                return vote.Error(f"No element at path: {self.selector}")

            if truthy(val):
                return Result.asvote(self.if_true, str(self))
        except ValueError as e:
            # Unable to convert to boolean
            return vote.Error(str(e))

        return Result.asvote(self.if_false, str(self))


class ContainsCondition(models.Model):
    selector = models.CharField(max_length=250)
    vals = models.TextField()
    if_true = models.IntegerField(choices=Result)
    if_false = models.IntegerField(choices=Result)
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
                return vote.Error(f"No elemenet at path: {self.selector}")

            val = str(val)
            if val in self.get_vals():
                return Result.asvote(self.if_true, str(self))
        except ValueError as e:
            # Unable to convert to string
            return vote.Error(str(e))

        return Result.asvote(self.if_false, str(self))
