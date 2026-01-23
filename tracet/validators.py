from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from tracet.models import GCNStream


def unique_stream_format(pk="pk"):
    def unique_stream_format(vals):
        if len(vals):
            notices = GCNStream.objects.filter(**{f"{pk}__in": vals})
            types = set(n.type for n in notices)
            if len(types) > 1:
                raise ValidationError(
                    _("Streams must be of a single type (currently contains %(types)s)"),
                    params={"types": ", ".join(t.upper() for t in types)}
                )

    return unique_stream_format