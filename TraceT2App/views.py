import logging

from django.core.paginator import EmptyPage, Paginator
from django.contrib import messages
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


# class TriggerCreate(View):
#     RangeFormSet = inlineformset_factory(
#         models.Trigger,
#         models.NumericRangeCondition,
#         fields=["val1", "selector", "val2"],
#         extra=1,
#     )

#     def get(self, request):
#         triggerform = forms.Trigger()
#         rangeformset = self.RangeFormSet()
#         return render(
#             request,
#             "TraceT2App/trigger/create.html",
#             {"form": triggerform, "rangeformset": rangeformset},
#         )

#     def post(self, request):
#         triggerform = forms.Trigger(request.POST)
#         rangeformset = self.RangeFormSet(request.POST)
#         if triggerform.is_valid():
#             trigger = triggerform.save()
#             return HttpResponseRedirect(trigger.get_absolute_url())
#         else:
#             return render(
#                 request,
#                 "TraceT2App/trigger/create.html",
#                 {"form": triggerform, rangeformset: "rangeformset"},
#             )


class TriggerBase(View):
    def setup(self, request, id=None):
        super().setup(request, id)

        try:
            self.trigger = models.Trigger.objects.get(id=id)
        except models.Trigger.DoesNotExist:
            self.trigger = None

        post = request.POST if request.POST else None

        self.forms = dict(
            triggerform=forms.Trigger(post, instance=self.trigger),
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
                models.MWA,
                form=forms.MWA,
                extra=0,
            )(post, instance=self.trigger),
            atcaformset=inlineformset_factory(
                models.Trigger,
                models.ATCA,
                form=forms.ATCA,
                extra=0,
            )(post, instance=self.trigger),
        )

        # ATCABandFormSet = inlineformset_factory(
        #     models.ATCA,
        #     models.ATCABand,
        #     form=forms.ATCABand,
        #     extra=0,
        # )

    def get(self, request, id=None):
        return render(
            request,
            "TraceT2App/trigger/edit.html",
            {"trigger": self.trigger, "title": self.title, "actionurl": self.actionurl}
            | self.forms,
        )

    def post(self, request, id=None):
        if all(map(lambda f: f.is_valid(), self.forms.values())):
            self.trigger = self.forms["triggerform"].save()
            for f in self.forms.values():
                f.save()

            messages.success(request, "Trigger was successfully updated.")
            return HttpResponseRedirect(self.trigger.get_absolute_url())
        else:
            messages.error(
                request, "The trigger could not be updated due to errors in the form."
            )
            return render(
                request,
                "TraceT2App/trigger/edit.html",
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

        self.forms["triggerform"].fields["streams"].disabled = True
        self.forms["triggerform"].fields["groupby"].disabled = True


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
                notice.decision = event.decisions.filter(
                    created__lte=notice.created, simulated=True
                ).first()

            event.form = forms.EventTrigger(initial={"eventid": event.id})

            event.realdecisions = event.decisions.filter(simulated=False).order_by(
                "created"
            )

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
