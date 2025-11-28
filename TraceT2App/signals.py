import datetime
import logging

import dateutil.parser
from django.db.models.signals import post_save, pre_save, m2m_changed
from django.dispatch import receiver

from TraceT2App import models


logger = logging.getLogger(__name__)

# TODO: post_save for models.Event: get_or_create Event for each existing trigger


@receiver(post_save, sender=models.Trigger)
def rebuild_events(sender, instance, created, **kwargs):
    """
    When a trigger is saved we do two things:

    1. If it's newly created, we created a list of associated events from the historical record.
    2. And whether is new or updated, we resimulate decisions.
    """
    trigger = instance

    # Create events out of historical record of notices
    if created:
        for notice in models.Notice.objects.filter(stream__in=trigger.streams.all()):
            trigger.get_or_create_event(notice)

    # Remove any existing simulated decision
    models.Decision.objects.filter(
        event__trigger_id=trigger.id, simulated=True
    ).delete()

    # Resimulate decisions at the time of each notice
    for event in trigger.event_set.all():
        for notice in event.notices.all():
            models.Decision.objects.create(
                event=event, simulated=True, created=notice.created
            )


@receiver(post_save, sender=models.Notice)
def update_events(sender, instance, created, **kwargs):
    """
    When a notice is created we must:

    1. Create (or update) an event for each Trigger, if the Trigger is listening to the notice's steam.
    2. Create a simulated and actual decision.
    """
    if not created:
        return

    notice = instance

    # For each trigger...
    for trigger in models.Trigger.objects.order_by("-priority"):
        if event := trigger.get_or_create_event(notice):
            # Create a simulated decision
            models.Decision.objects.create(
                event=event, simulated=True, created=notice.created
            )

            # And if this is a real notice, run the trigger for real
            if not notice.istest:
                event.runtrigger()


@receiver(m2m_changed, sender=models.Event.notices.through)
def event_updatetime(sender, instance, pk_set, action, reverse, **kwargs):
    """
    For each new notice added to an event, update the Event.time field to reflect
    the _earliest_ `trigger.time_path` value.
    """
    if reverse is False and action == "post_add":
        event = instance
        for notice in models.Notice.objects.filter(id__in=pk_set):
            try:
                t = dateutil.parser.parse(
                    notice.query(event.trigger.time_path),
                    default=datetime.datetime(1900, 1, 1, tzinfo=datetime.UTC),
                )
                if event.time is None:
                    event.time = t
                else:
                    event.time = min(t, event.time)
            except Exception:
                pass

        event.save()
