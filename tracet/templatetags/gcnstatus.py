import datetime

from django import template
from django.core.cache import cache
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def gcnstatus(**kwargs):
    received = cache.get(
        "gcn_heartbeat_received",
        default=datetime.datetime(1900, 1, 1, tzinfo=datetime.UTC),
    )

    lag = datetime.datetime.now(datetime.UTC) - received

    if lag < datetime.timedelta(seconds=5):
        return mark_safe(
            f'<code title="Last heartbeat was received {lag.microseconds / 1e6:.1f} seconds ago">Stream OK <span class="gcn-status ok">OK</span></code>'
        )
    elif lag < datetime.timedelta(seconds=60):
        return mark_safe(
            f'<code title="Last heartbeat was received {lag.microseconds / 1e6:.1f} seconds ago">Stream DELAYED <span class="gcn-status delayed">Delayed</span></code>'
        )
    else:
        return mark_safe(
            f'<code title="Last heartbeat was received {lag.microseconds / 1e6:.1f} seconds ago">Stream FAILURE <span class="gcn-status fail">Failed</span></code>'
        )
