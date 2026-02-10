from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from tracet.models import Topic


def unique_topic_format(pk="pk"):
    def unique_topic_format(vals):
        if len(vals):
            notices = Topic.objects.filter(**{f"{pk}__in": vals})
            types = set(n.type for n in notices)
            if len(types) > 1:
                raise ValidationError(
                    _("Topics must be of a single format (currently contains %(types)s)"),
                    params={"types": ", ".join(t.upper() for t in types)}
                )

    return unique_topic_format