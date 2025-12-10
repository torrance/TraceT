import json

from django import forms
from lxml import etree

from . import models


class DateInput(forms.DateInput):
    input_type = "date"


class DateTimeInput(forms.DateTimeInput):
    input_type = "datetime-local"


class Trigger(forms.ModelForm):
    class Meta:
        model = models.Trigger
        fields = ["active", "streams", "groupby", "ra_path", "dec_path", "time_path"]


class NumericRangeCondition(forms.ModelForm):
    template_name = "TraceT2App/forms/numericrangecondition.html"

    class Meta:
        model = models.NumericRangeCondition
        fields = ["val1", "selector", "val2", "if_true", "if_false"]
        widgets = {
            "val1": forms.NumberInput(attrs={"placeholder": "Lower"}),
            "val2": forms.NumberInput(attrs={"placeholder": "Upper"}),
            "selector": forms.TextInput(attrs={"placeholder": "Selector"}),
        }


NumericRangeCondition.Meta.error_messages = {
    field: {
        "required": f"{getattr(models.NumericRangeCondition, field).field.verbose_name.capitalize()} is required"
    }
    for field in NumericRangeCondition.Meta.fields
}


class BooleanCondition(forms.ModelForm):
    template_name = "TraceT2App/forms/base.html"

    class Meta:
        model = models.BooleanCondition
        fields = ["selector", "if_true", "if_false"]
        widgets = {"selector": forms.TextInput(attrs={"placeholder": "Selector"})}


BooleanCondition.Meta.error_messages = {
    field: {
        "required": f"{getattr(models.BooleanCondition, field).field.verbose_name.capitalize()} is required"
    }
    for field in BooleanCondition.Meta.fields
}


class MWA(forms.ModelForm):
    template_name = "TraceT2App/forms/base.html"

    class Meta:
        model = models.MWA
        fields = [
            "projectid",
            "secure_key",
            "tileset",
            "frequency",
            "frequency_resolution",
            "time_resolution",
            "exposure",
            "nobs",
            "maximum_window",
        ]


MWA.Meta.error_messages = {
    field: {
        "required": f"{getattr(models.MWA, field).field.verbose_name.capitalize()} is required"
    }
    for field in MWA.Meta.fields
}


class ATCA(forms.ModelForm):
    template_name = "TraceT2App/forms/base.html"

    class Meta:
        model = models.ATCA
        fields = [
            "projectid",
            "http_username",
            "http_password",
            "email",
            "authentication_token",
            "maximum_lag",
            "minimum_exposure",
            "maximum_exposure",
        ]


ATCA.Meta.error_messages = {
    field: {
        "required": f"{getattr(models.ATCA, field).field.verbose_name.capitalize()} is required"
    }
    for field in ATCA.Meta.fields
}


class ATCABand(forms.ModelForm):
    template_name = "TraceT2App/forms/base.html"

    class Meta:
        model = models.ATCABand
        fields = [
            "band",
            "freq1",
            "freq2",
            "exposure",
        ]


ATCABand.Meta.error_messages = {
    field: {
        "required": f"{getattr(models.ATCABand, field).field.verbose_name.capitalize()} is required"
    }
    for field in ATCABand.Meta.fields
}


class Notice(forms.Form):
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
        super().clean()

        n = models.Notice(
            stream=self.cleaned_data["stream"],
            payload=self.cleaned_data["payload"].encode(),
        )
        try:
            n.query(".")
        except etree.XMLSyntaxError:
            raise forms.ValidationError(
                "Unable to parse the payload as XML", code="invalid"
            )
        except json.JSONDecodeError:
            raise forms.ValidationError(
                "Unable to parse the payload as JSON", code="invalid"
            )


class EventTrigger(forms.Form):
    eventid = forms.IntegerField(widget=forms.HiddenInput)
