import logging

from django.core.paginator import EmptyPage, Paginator
from django.forms import formset_factory, modelformset_factory, inlineformset_factory
from django.shortcuts import (
    render,
    get_object_or_404,
    get_list_or_404,
    HttpResponseRedirect,
    resolve_url,
)
from django.views import View

from . import models, forms, filters


logger = logging.getLogger(__name__)


class Event(View):
    def get(self, request, id):
        event = get_object_or_404(models.Event, id=id)
        return render(
            request,
            "TraceT2App/event/get.html",
            {"event": event},
        )


class EventList(View):
    def get(self, request):
        filter = filters.Event(request.GET, models.Event.objects.order_by("-created"))

        paginator = Paginator(filter.qs, 100)
        pagenumber = request.GET.get("page", 1)

        try:
            events = paginator.page(pagenumber)
        except EmptyPage:
            # If out of range, display last page
            events = paginator.page(paginator.num_pages)

        return render(
            request, "TraceT2App/event/list.html", {"events": events, "filter": filter}
        )


class EventCreate(View):
    def get(self, request):
        form = forms.Event()
        return render(request, "TraceT2App/event/create.html", {"form": form})

    def post(self, request):
        form = forms.Event(request.POST)

        if form.is_valid():
            e = models.Event(
                stream=form.cleaned_data["stream"],
                created=form.cleaned_data["created"],
                payload=form.cleaned_data["payload"].encode(),
                istest=True,
            )
            e.full_clean()
            e.save()

            return HttpResponseRedirect(e.get_absolute_url())
        else:
            return render(request, "TraceT2App/event/create.html", {"form": form})


class TriggerCreate(View):
    RangeFormSet = inlineformset_factory(
        models.Trigger,
        models.NumericRangeCondition,
        fields=["val1", "selector", "val2"],
        extra=1,
    )

    def get(self, request):
        triggerform = forms.Trigger()
        rangeformset = self.RangeFormSet()
        return render(
            request,
            "TraceT2App/trigger/create.html",
            {"form": triggerform, "rangeformset": rangeformset},
        )

    def post(self, request):
        triggerform = forms.Trigger(request.POST)
        rangeformset = self.RangeFormSet(request.POST)
        if triggerform.is_valid():
            trigger = triggerform.save()
            return HttpResponseRedirect(trigger.get_absolute_url())
        else:
            return render(
                request,
                "TraceT2App/trigger/create.html",
                {"form": triggerform, rangeformset: "rangeformset"},
            )


class TriggerEdit(View):
    RangeFormSet = inlineformset_factory(
        models.Trigger,
        models.NumericRangeCondition,
        fields=["val1", "selector", "val2", "if_true", "if_false"],
        extra=1,
    )

    BooleanFormSet = inlineformset_factory(
        models.Trigger,
        models.BooleanCondition,
        fields=["selector", "if_true", "if_false"],
        extra=1,
    )

    def get(self, request, id):
        trigger = get_object_or_404(models.Trigger, id=id)
        triggerform = forms.Trigger(instance=trigger)
        rangeformset = self.RangeFormSet(instance=trigger)
        booleanformset = self.BooleanFormSet(instance=trigger)

        return render(
            request,
            "TraceT2App/trigger/edit.html",
            {
                "form": triggerform,
                "rangeformset": rangeformset,
                "booleanformset": booleanformset,
                "trigger": trigger,
            },
        )

    def post(self, request, id):
        trigger = get_object_or_404(models.Trigger, id=id)
        triggerform = forms.Trigger(request.POST, instance=trigger)
        rangeformset = self.RangeFormSet(request.POST, instance=trigger)
        booleanformset = self.BooleanFormSet(request.POST, instance=trigger)

        if (
            triggerform.is_valid()
            and rangeformset.is_valid()
            and booleanformset.is_valid()
        ):
            trigger = triggerform.save()
            rangeformset.save()
            booleanformset.save()
            return HttpResponseRedirect(trigger.get_absolute_url())
        else:
            return render(
                request,
                "TraceT2App/trigger/edit.html",
                {
                    "form": triggerform,
                    "rangeformset": rangeformset,
                    "booleanformset": booleanformset,
                    "trigger": trigger,
                },
            )


class Trigger(View):
    def get(self, request, id):
        trigger = get_object_or_404(
            models.Trigger,
            id=id,
        )

        eventgroups = trigger.eventgroup_set.order_by("-time")

        for eventgroup in eventgroups:
            events = []
            for event in eventgroup.events.order_by("created"):
                event.pointing = eventgroup.pointing(attime=event.created)
                event.votes = eventgroup.evaluateconditions(attime=event.created)
                events.append(event)

            eventgroup.eventss = events

        return render(
            request,
            "TraceT2App/trigger/get.html",
            {
                "trigger": trigger,
                "conditions": trigger.get_conditions(),
                "eventgroups": eventgroups,
            },
        )
