import json

from django import forms
from lxml import etree

from . import models


class DateInput(forms.DateInput):
    input_type = "date"


class DateTimeInput(forms.DateTimeInput):
    input_type = "datetime-local"


class Trigger(forms.ModelForm):
    # active = forms.BooleanField(
    #     label="Is trigger active?"
    # )

    # streams = forms.MultipleChoiceField(
    #     label="GCN Streams"
    # )

    class Meta:
        model = models.Trigger
        fields = ["active", "streams", "groupby"]
        widgets = {
            # "streams": forms.CheckboxSelectMultiple
        }


class NumericRangeCondition(forms.ModelForm):
    class Meta:
        model = models.NumericRangeCondition
        fields = ["selector", "val1", "val2"]


class EventFilter(forms.Form):
    stream = forms.ModelMultipleChoiceField(
        label="Stream",
        queryset=models.GCNStream.objects.order_by("name"),
        required=False,
    )


class Event(forms.Form):
    stream = forms.ModelChoiceField(
        queryset=models.GCNStream.objects.order_by("name"),
        required=True,
        help_text="Select the matching stream of the notice.",
    )
    created = forms.DateTimeField(
        required=True,
        widget=DateTimeInput,
        help_text="Set the created date and time to match the true time of the notice.",
    )
    payload = forms.CharField(
        widget=forms.Textarea,
        help_text=(
            "Paste in the full XML or JSON string, depending on the file type of the chosen stream."
        ),
        required=True,
    )

    def clean(self):
        e = models.Event(
            stream=self.cleaned_data["stream"],
            payload=self.cleaned_data["payload"].encode(),
        )
        try:
            e.query(".")
        except etree.XMLSyntaxError:
            raise forms.ValidationError(
                "Unable to parse the payload as XML", code="invalid"
            )
        except json.JSONDecodeError:
            raise forms.ValidationError(
                "Unable to parse the payload as JSON", code="invalid"
            )
