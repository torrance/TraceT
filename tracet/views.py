import logging

from django.core.paginator import EmptyPage, Paginator
from django.contrib import messages
from django.contrib.auth import get_user
from django.forms import formset_factory, modelformset_factory, inlineformset_factory
from django.shortcuts import (
    get_object_or_404,
    get_list_or_404,
    render,
    resolve_url,
    HttpResponseRedirect,
    HttpResponse,
)
from django.urls import reverse
from django.views import View

from . import models, forms, filters


logger = logging.getLogger(__name__)


class Notice(View):
    def get(self, request, id):
        notice = get_object_or_404(models.Notice, id=id)
        return render(
            request,
            "tracet/notice/get.html",
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
            "tracet/notice/list.html",
            {"notices": notices, "filter": filter},
        )


class NoticeCreate(View):
    def get(self, request):
        form = forms.Notice()
        return render(request, "tracet/notice/create.html", {"form": form})

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
            return render(request, "tracet/notice/create.html", {"form": form})


class ObservationList(View):
    def get(self, request):
        filter = filters.Observation(
            request.GET,
            models.Observation.objects.order_by("-created"),
        )

        paginator = Paginator(filter.qs, 100)
        pagenumber = request.GET.get("page", 1)

        try:
            observations = paginator.page(pagenumber)
        except EmptyPage:
            # If out of range, display last page
            observations = paginator.page(paginator.num_pages)

        return render(
            request,
            "tracet/observation/list.html",
            {"observations": observations, "filter": filter},
        )


class ObservationView(View):
    def get(self, request, id):
        observation = get_object_or_404(models.Observation, id=id)
        return render(
            request,
            "tracet/observation/get.html",
            {"observation": observation},
        )


class TriggerList(View):
    TriggerFormset = modelformset_factory(
        models.Trigger,
        form=forms.TriggerAdmin,
        extra=0,
        edit_only=True,
    )

    def get(self, request):
        activetriggers = self.TriggerFormset(
            prefix="activetriggers",
            queryset=models.Trigger.objects.order_by("-priority").filter(active=True),
        )
        inactivetriggers = self.TriggerFormset(
            prefix="inactivetriggers",
            queryset=models.Trigger.objects.order_by("-priority").filter(active=False),
        )

        return render(
            request,
            "tracet/trigger/list.html",
            {"activetriggers": activetriggers, "inactivetriggers": inactivetriggers},
        )

    def post(self, request):
        activetriggers = self.TriggerFormset(request.POST, prefix="activetriggers")
        inactivetriggers = self.TriggerFormset(request.POST, prefix="inactivetriggers")

        if activetriggers.is_valid() and inactivetriggers.is_valid():
            activetriggers.save()
            inactivetriggers.save()
            messages.success(
                request,
                "Trigger statuses and priorities have been successfully updated.",
            )
            return HttpResponseRedirect(reverse("triggers"))
        else:
            messages.success(
                request,
                "Trigger statusesand/or priorities could not be updated due to a form error.",
            )
            return render(
                request,
                "tracet/trigger/list.html",
                {
                    "activetriggers": activetriggers,
                    "inactivetriggers": inactivetriggers,
                },
            )


class TriggerBase(View):
    def setup(self, request, id=None):
        super().setup(request, id)

        if id is not None:
            self.trigger = get_object_or_404(models.Trigger, id=id)
        else:
            self.trigger = None

        post = request.POST if request.POST else None
        user = get_user(request) if self.trigger is None else self.trigger.user

        self.forms = dict(
            triggerform=forms.Trigger(
                post, initial={"user": user}, instance=self.trigger
            ),
            rangeformset=inlineformset_factory(
                models.Trigger,
                models.NumericRangeCondition,
                form=forms.NumericRangeCondition,
                extra=0,
            )(post, instance=self.trigger),
            booleanformset=inlineformset_factory(
                models.Trigger,
                models.BooleanCondition,
                form=forms.BooleanCondition,
                extra=0,
            )(post, instance=self.trigger),
            mwaformset=inlineformset_factory(
                models.Trigger,
                models.MWACorrelator,
                form=forms.MWACorrelator,
                extra=0,
            )(post, instance=self.trigger),
            mwagwformset=inlineformset_factory(
                models.Trigger,
                models.MWAGW,
                form=forms.MWAGW,
                extra=0,
            )(post, instance=self.trigger),
            mwavcsformset=inlineformset_factory(
                models.Trigger,
                models.MWAVCS,
                form=forms.MWAVCS,
                extra=0,
            )(post, instance=self.trigger),
            atcaformset=inlineformset_factory(
                models.Trigger,
                models.ATCA,
                form=forms.ATCA,
                formset=forms.BaseATCAWithBandsFormset,
                extra=0,
            )(post, instance=self.trigger),
        )

    def get(self, request, id=None):
        return render(
            request,
            "tracet/trigger/edit.html",
            {"trigger": self.trigger, "title": self.title, "actionurl": self.actionurl}
            | self.forms,
        )

    def post(self, request, id=None):
        if all(map(lambda f: f.is_valid(), self.forms.values())):
            # Save the parent trigger first
            self.trigger = self.forms["triggerform"].save()
            for name, form in self.forms.items():
                # Then for save each child element, careful to assign the instance in
                # the case that trigger is new.
                if name != "triggerform":
                    form.instance = self.trigger
                    form.save()

            messages.success(request, "Trigger was successfully updated.")
            return HttpResponseRedirect(self.trigger.get_absolute_url())
        else:
            messages.error(
                request, "The trigger could not be updated due to errors in the form."
            )
            return render(
                request,
                "tracet/trigger/edit.html",
                {
                    "trigger": self.trigger,
                    "title": self.title,
                    "actionurl": self.actionurl,
                }
                | self.forms,
            )


class TriggerCreate(TriggerBase):
    def setup(self, request):
        super().setup(request)
        self.title = "Create a new trigger"
        self.actionurl = reverse("triggercreate")

        del self.forms["triggerform"].fields["active"]


class TriggerUpdate(TriggerBase):
    def setup(self, request, id):
        super().setup(request, id)
        self.title = f"Update {self.trigger.name}"
        self.actionurl = reverse("triggeredit", args=[id])


class TriggerDelete(View):
    def post(self, request, id):
        trigger = get_object_or_404(models.Trigger, id=id)
        trigger.delete()

        messages.success(request, "Trigger was deleted")
        return HttpResponseRedirect(reverse("home"))


class TriggerView(View):
    def get(self, request, id):
        trigger = get_object_or_404(models.Trigger, id=id)

        events = trigger.event_set.order_by("-time")

        for event in events:
            event.noticess = list(event.notices.order_by("created"))
            for notice in event.noticess:
                decision, _ = models.Decision.objects.get_or_create(
                    event=event,
                    created=notice.created,
                    source=models.Decision.Source.SIMULATED,
                )
                notice.decision = decision

            event.form = forms.EventTrigger(initial={"eventid": event.id})

            event.realdecisions = event.decisions.exclude(
                source=models.Decision.Source.SIMULATED
            ).order_by("created")

        return render(
            request,
            "tracet/trigger/get.html",
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
            event = trigger.event_set.get(id=form.cleaned_data["eventid"])
            models.Decision.objects.create(
                event=event, source=models.Decision.Source.MANUAL
            )

            return HttpResponseRedirect(trigger.get_absolute_url())
        else:
            return HttpResponse("Bad Request", status=400)
