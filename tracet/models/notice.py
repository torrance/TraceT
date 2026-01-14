import io
import logging
import json

import jsonpath_rfc9535 as jsonpath
from lxml import etree

from django.db import models
from django.urls import reverse
from django.utils import timezone


logger = logging.getLogger(__name__)


class GCNStream(models.Model):
    class Format(models.TextChoices):
        XML = ("xml", "XML")
        JSON = ("json", "JSON")

    name = models.CharField(max_length=500, unique=True)
    type = models.CharField(max_length=500, choices=Format, default="xml")

    def __str__(self):
        return self.name


class Notice(models.Model):
    stream = models.ForeignKey(
        "GCNStream", related_name="notices", on_delete=models.CASCADE
    )
    created = models.DateTimeField(default=timezone.now)
    payload = models.BinaryField()
    istest = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created"]
        indexes = [models.Index(fields=["-created"])]

    def __str__(self):
        return str(self.stream)

    def get_absolute_url(self):
        return reverse("notice", args=[self.id])

    def file_type(self):
        return self.stream.get_type_display()

    def query(self, path):
        # Handle empty paths gracefully
        if not path:
            return None

        try:
            if self.stream.type == "xml":
                rootnode = etree.parse(io.BytesIO(self.payload)).getroot()
                return rootnode.xpath(path, namespaces=rootnode.nsmap)[0]
            elif self.stream.type == "json":
                return jsonpath.find(path, json.loads(self.payload))[0].value
        except IndexError:
            # In the case that no value is found at the path, we return None
            return None
        except etree.XPathEvalError as e:
            logger.error(f"Malformed XML query: {path} ({str(e)})")
            return None

    def pretty_payload(self):
        if self.stream.type == "xml":
            return etree.tostring(
                etree.parse(io.BytesIO(self.payload)), pretty_print=True
            ).decode()
        elif self.stream.type == "json":
            return json.dumps(json.loads(self.payload), indent=4)
