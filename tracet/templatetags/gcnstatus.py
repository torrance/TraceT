import datetime

from django import template
from django.core.cache import cache
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def gcnstatus(**kwargs):
    lastseen = cache.get(
        "gcn_last_seen", default=datetime.datetime(1900, 1, 1, tzinfo=datetime.UTC)
    )
    if datetime.datetime.now(datetime.UTC) - lastseen > datetime.timedelta(seconds=15):
        return mark_safe(f'<code title="Last seen heartbeat: {lastseen}">Stream FAILURE <span class="gcn-status fail">Failed</span></code>')
    else:
        return mark_safe(f'<code title="Last seen heartbeat: {lastseen}">Stream OK <span class="gcn-status ok">OK</span></code>')
