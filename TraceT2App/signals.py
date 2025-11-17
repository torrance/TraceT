import datetime
import logging

import dateutil.parser
from django.db.models.signals import post_save, pre_save, m2m_changed
from django.dispatch import receiver

from . import models


logger = logging.getLogger(__name__)

# TODO: post_save for models.Event: get_or_create EventGroup for each existing trigger


@receiver(post_save, sender=models.Trigger)
def rebuild_eventgroups(sender, instance, **kwargs):
    # Delete all event groups attached to this trigger
    models.EventGroup.objects.filter(trigger=instance).delete()

    # ...and rebuild them
    groupby = instance.groupby
    for event in models.Event.objects.filter(stream__in=instance.streams.all()):
        groupid = event.query(groupby)
        if groupid:
            logger.warning("GroupID = %s", groupid)

            eventgroup, _ = models.EventGroup.objects.get_or_create(
                groupid=groupid, trigger=instance
            )

            eventgroup.events.add(event)
            eventgroup.save()
        else:
            logger.warning(f"Rebuilding eventgroup for Trigger(id={instance.id}) but unable to query groupid on event(id={event.id})")


@receiver(post_save, sender=models.Event)
def attach_to_eventgroups(sender, instance, **kwargs):
    for trigger in models.Trigger.objects.all():
        if trigger.streams.filter(id=instance.stream.id).exists():
            if (groupid := instance.query(trigger.groupby)):
                eventgroup, _ = models.EventGroup.objects.get_or_create(
                    groupid=groupid, trigger=trigger
                )
                eventgroup.events.add(instance)
                eventgroup.save()
            else:
                logger.warning(f"Processing new event(id={instance.id}) for Trigger(id={trigger.id}) but unable to query groupid")



@receiver(m2m_changed, sender=models.EventGroup.events.through)
def eventgroup_updatetime(sender, instance, **kwargs):
    for event in models.Event.objects.filter(id__in=kwargs["pk_set"]):
        try:
            t = dateutil.parser.parse(
                event.query(instance.trigger.time_path),
                default=datetime.datetime(1900, 1, 1, tzinfo=datetime.UTC),
            )
            if instance.time is None:
                instance.time = t
            else:
                instance.time = min(t, instance.time)
        except Exception:
            pass
