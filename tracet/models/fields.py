from lxml import etree
import jsonpath_rfc9535 as jsonpath

from django.core.exceptions import ValidationError
from django.db import models


class JXPathField(models.CharField):
    def __init__(self, gettype=None, *args, **kwargs):
        kwargs.pop("max_length", None)  # Required to allow migrations to keep working
        super().__init__(max_length=500, *args, **kwargs)

        self.gettype = gettype

    def validate(self, value, model_instance):
        super().validate(value, model_instance)

        format = self.gettype(model_instance)
        try:
            if format == "xml":
                etree.XPath(value)
            elif format == "json":
                jsonpath.compile(value)
        except etree.XPathSyntaxError:
            raise ValidationError("Invalid XPath selector", "invalid")
        except jsonpath.JSONPathSyntaxError:
            raise ValidationError("Invalid JPath selector", "invalid")
