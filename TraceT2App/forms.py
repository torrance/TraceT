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
        fields = ["name", "active", "streams", "groupby", "time_path"]


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


class MWACorrelator(forms.ModelForm):
    template_name = "TraceT2App/forms/base.html"

    class Meta:
        model = models.MWACorrelator
        fields = [
            "projectid",
            "secure_key",
            "ra_path",
            "dec_path",
            "tileset",
            "frequency",
            "frequency_resolution",
            "time_resolution",
            "exposure",
            "nobs",
            "maximum_window",
            "repointing_threshold",
        ]


MWACorrelator.Meta.error_messages = {
    field: {
        "required": f"{getattr(models.MWACorrelator, field).field.verbose_name.capitalize()} is required"
    }
    for field in MWACorrelator.Meta.fields
}


class MWAVCS(forms.ModelForm):
    template_name = "TraceT2App/forms/base.html"

    class Meta:
        model = models.MWAVCS
        fields = [
            "projectid",
            "secure_key",
            "ra_path",
            "dec_path",
            "tileset",
            "frequency",
            "frequency_resolution",
            "time_resolution",
            "exposure",
            "nobs",
            "maximum_window",
            "repointing_threshold",
        ]


MWAVCS.Meta.error_messages = {
    field: {
        "required": f"{getattr(models.MWAVCS, field).field.verbose_name.capitalize()} is required"
    }
    for field in MWAVCS.Meta.fields
}


class MWAGW(forms.ModelForm):
    template_name = "TraceT2App/forms/base.html"

    class Meta:
        model = models.MWAGW
        fields = [
            "projectid",
            "secure_key",
            "skymap_path",
            "tileset",
            "frequency",
            "frequency_resolution",
            "time_resolution",
            "exposure",
            "nobs",
            "maximum_window",
            "repointing_threshold",
        ]


MWAGW.Meta.error_messages = {
    field: {
        "required": f"{getattr(models.MWAGW, field).field.verbose_name.capitalize()} is required"
    }
    for field in MWAGW.Meta.fields
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
            "ra_path",
            "dec_path",
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


class BaseATCAWithBandsFormset(forms.BaseInlineFormSet):
    """
    This class helps us make doubly-nested formsets.
    Adapted from: https://github.com/philgyford/django-nested-inline-formsets-example
    """

    def add_fields(self, form, index):
        super().add_fields(form, index)

        # Save the formset for a Book's Images in the nested property.
        ATCABandSet = forms.inlineformset_factory(
            models.ATCA, models.ATCABand, form=ATCABand, extra=1
        )

        form.nested = ATCABandSet(
            instance=form.instance,
            data=form.data if form.is_bound else None,
            files=form.files if form.is_bound else None,
            prefix="%s-%s" % (form.prefix, ATCABandSet.get_default_prefix()),
        )

    def is_valid(self):
        """
        Also validate the nested formsets.
        """
        result = super().is_valid()

        if self.is_bound:
            for form in self.forms:
                if hasattr(form, "nested"):
                    result = result and form.nested.is_valid()

        return result

    def clean(self):
        """
        If a parent form has no data, but its nested forms do, we should
        return an error, because we can't save the parent.
        For example, if the Book form is empty, but there are Images.
        """
        super().clean()

        for form in self.forms:
            if not hasattr(form, "nested") or self._should_delete_form(form):
                continue

            if self._is_adding_nested_inlines_to_empty_form(form):
                form.add_error(
                    field=None,
                    error="You cannot add ATCA bands to a missing ATCA configuration.",
                )

    def save(self, commit=True):
        """
        Also save the nested formsets.
        """
        result = super().save(commit=commit)

        for form in self.forms:
            if hasattr(form, "nested"):
                if not self._should_delete_form(form):
                    form.nested.save(commit=commit)

        return result

    def _is_adding_nested_inlines_to_empty_form(self, form):
        """
        Are we trying to add data in nested inlines to a form that has no data?
        e.g. Adding Images to a new Book whose data we haven't entered?
        """
        if not hasattr(form, "nested"):
            # A basic form; it has no nested forms to check.
            return False

        if self._is_form_persisted(form):
            # We're editing (not adding) an existing model.
            return False

        if not self._is_empty_form(form):
            # The form has errors, or it contains valid data.
            return False

        # All the inline forms that aren't being deleted:
        non_deleted_forms = set(form.nested.forms).difference(
            set(form.nested.deleted_forms)
        )

        # At this point we know that the "form" is empty.
        # In all the inline forms that aren't being deleted, are there any that
        # contain data? Return True if so.
        return any(
            not self.is_empty_form(nested_form) for nested_form in non_deleted_forms
        )

    def _is_empty_form(self, form):
        """
        A form is considered empty if it passes its validation,
        but doesn't have any data.

        This is primarily used in formsets, when you want to
        validate if an individual form is empty (extra_form).
        """
        return form.is_valid() and not form.cleaned_data

    def _is_form_persisted(selfg, form):
        """
        Does the form have a model instance attached and it's not being added?
        e.g. The form is about an existing Book whose data is being edited.
        """
        return form.instance and not form.instance._state.adding


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
