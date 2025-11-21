import datetime
import logging

import dateutil.parser
from django.db.models.signals import post_save, pre_save, m2m_changed
from django.dispatch import receiver

from . import models


logger = logging.getLogger(__name__)

# TODO: post_save for models.Event: get_or_create Event for each existing trigger


@receiver(post_save, sender=models.Trigger)
def rebuild_events(sender, instance, **kwargs):
    # Delete all event groups attached to this trigger
    models.Event.objects.filter(trigger=instance).delete()

    # ...and rebuild them
    groupby = instance.groupby
    for notice in models.Notice.objects.filter(stream__in=instance.streams.all()):
        groupid = notice.query(groupby)
        if groupid:
            logger.warning("GroupID = %s", groupid)

            event, _ = models.Event.objects.get_or_create(
                groupid=groupid, trigger=instance
            )

            event.notices.add(notice)
            event.save()
        else:
            logger.warning(f"Rebuilding event for Trigger(id={instance.id}) but unable to query groupid on notice(id={notice.id})")


@receiver(post_save, sender=models.Notice)
def attach_to_events(sender, instance, **kwargs):
    for trigger in models.Trigger.objects.all():
        if trigger.streams.filter(id=instance.stream.id).exists():
            if (groupid := instance.query(trigger.groupby)):
                # Attach notice to Event
                event, _ = models.Event.objects.get_or_create(
                    groupid=groupid, trigger=trigger
                )
                event.notices.add(instance)
                event.save()

                # Run conditions
                event.runtrigger()
            else:
                logger.warning(f"Processing new notice(id={instance.id}) for Trigger(id={trigger.id}) but unable to query groupid")



@receiver(m2m_changed, sender=models.Event.notices.through)
def event_updatetime(sender, instance, **kwargs):
    for notice in models.Notice.objects.filter(id__in=kwargs["pk_set"]):
        try:
            t = dateutil.parser.parse(
                notice.query(instance.trigger.time_path),
                default=datetime.datetime(1900, 1, 1, tzinfo=datetime.UTC),
            )
            if instance.time is None:
                instance.time = t
            else:
                instance.time = min(t, instance.time)
        except Exception:
            pass
