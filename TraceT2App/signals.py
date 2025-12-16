import logging

from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver

from TraceT2App import models


logger = logging.getLogger(__name__)


@receiver(post_save, sender=models.Trigger)
def on_trigger_save(sender, instance, created, **kwargs):
    """
    When a trigger is saved:
    1. If the trigger is newly created, we need to create associated events from the archive of notices.
    2. Resync each event's time in case time_path has been updated.
    """
    trigger = instance

    # Create events that match the stream and groupby criteria
    if created:
        for notice in models.Notice.objects.filter(stream__in=trigger.streams.all()):
            event = trigger.get_or_create_event(notice)

    # Set or update (where Trigger.time_path has changed) event time
    for event in trigger.event_set.all():
        event.updatetime()


@receiver(post_save, sender=models.Notice)
def on_notice_save(sender, instance, created, **kwargs):
    """
    When a notice is created we must:

    1. Create (or update) an event for each Trigger, if the Trigger is listening to the notice's steam.
    2. Run each applicable trigger.
    """
    notice = instance

    if not created:
        return

    # For each trigger...
    for trigger in models.Trigger.objects.order_by("-priority"):
        # (Maybe) create a new event
        if event := trigger.get_or_create_event(notice):
            # If this is a real notice, run the trigger for real
            if not notice.istest:
                models.Decision.objects.create(
                    event=event, source=models.Decision.Source.NOTICE
                )


@receiver(post_save, sender=models.NumericRangeCondition)
def on_condition_save(sender, instance, created, **kwargs):
    """
    When a Trigger's condition changes, we clear out prior simulated decisions
    This will be automatically generated when needed.
    """
    trigger = instance.trigger
    models.Decision.objects.filter(
        event__trigger__id=trigger.id, source=models.Decision.Source.SIMULATED
    ).delete()


@receiver(m2m_changed, sender=models.Event.notices.through)
def no_event_notices_changed(sender, instance, pk_set, action, reverse, **kwargs):
    """
    For each new notice added to an event, update the Event.time field to reflect
    the _earliest_ `trigger.time_path` value.
    """
    event = instance

    if reverse is False and action == "post_add":
        event.updatetime()
