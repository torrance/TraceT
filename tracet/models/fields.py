from lxml import etree
import jsonpath_rfc9535 as jsonpath

from django.core.exceptions import ValidationError
from django.db import models


class JXPathField(models.CharField):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def validate(self, value, model_instance):
        super().validate(value, model_instance)

        # We assume the streams are an homogenous type
        format = model_instance.trigger.streams.first().type

        try:
            if format == "xml":
                etree.XPath(value)
            elif format == "json":
                jsonpath.compile(value)
        except etree.XPathSyntaxError:
            raise ValidationError("Invalid XPath selector", "invalid")
        except jsonpath.JSONPathSyntaxError:
            raise ValidationError("Invalid JPath selector", "invalid")
