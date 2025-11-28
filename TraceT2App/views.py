import logging

from django.core.paginator import EmptyPage, Paginator
from django.forms import formset_factory, modelformset_factory, inlineformset_factory
from django.shortcuts import (
    get_object_or_404,
    get_list_or_404,
    render,
    resolve_url,
    HttpResponseRedirect,
    HttpResponse,
)
from django.views import View

from . import models, forms, filters


logger = logging.getLogger(__name__)


class Notice(View):
    def get(self, request, id):
        notice = get_object_or_404(models.Notice, id=id)
        return render(
            request,
            "TraceT2App/notice/get.html",
            {"notice": notice},
        )


class NoticeList(View):
    def get(self, request):
        filter = filters.Notice(
            request.GET,
            models.Notice.objects.order_by("-created").select_related("stream"),
        )

        paginator = Paginator(filter.qs, 100)
        pagenumber = request.GET.get("page", 1)

        try:
            notices = paginator.page(pagenumber)
        except EmptyPage:
            # If out of range, display last page
            notices = paginator.page(paginator.num_pages)

        return render(
            request,
            "TraceT2App/notice/list.html",
            {"notices": notices, "filter": filter},
        )


class NoticeCreate(View):
    def get(self, request):
        form = forms.Notice()
        return render(request, "TraceT2App/notice/create.html", {"form": form})

    def post(self, request):
        form = forms.Notice(request.POST)

        if form.is_valid():
            n = models.Notice(
                stream=form.cleaned_data["stream"],
                created=form.cleaned_data["created"],
                payload=form.cleaned_data["payload"].encode(),
                istest=True,
            )
            n.full_clean()
            n.save()

            return HttpResponseRedirect(n.get_absolute_url())
        else:
            return render(request, "TraceT2App/notice/create.html", {"form": form})


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
        trigger = get_object_or_404(models.Trigger, id=id)

        events = trigger.event_set.order_by("-time")

        for event in events:
            event.noticess = list(event.notices.order_by("created"))
            for notice in event.noticess:
                notice.decision = event.decisions.filter(
                    created__lte=notice.created, simulated=True
                ).first()

            event.form = forms.EventTrigger(initial={"eventid": event.id})

        return render(
            request,
            "TraceT2App/trigger/get.html",
            {
                "trigger": trigger,
                "conditions": trigger.get_conditions(),
                "events": events,
            },
        )

    def post(self, request, id):
        trigger = get_object_or_404(models.Trigger, id=id)

        form = forms.EventTrigger(request.POST)

        if form.is_valid():
            trigger.event_set.get(id=form.cleaned_data["eventid"]).runtrigger()

            return HttpResponseRedirect(trigger.get_absolute_url())
        else:
            return HttpResponse("Bad Request", status=400)
