import json
import logging

import dateutil.parser

from django.core.cache import cache
from django.core.management.base import BaseCommand
from gcn_kafka import Consumer

from tracet.models import Notice, GCNStream

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Start listening to GCN notices"

    def handle(self, *args, **kwargs):
        # We periodically reconnect to GCN every ~10 minutes so that we pick up any
        # new streams that may have been added in the meantime.
        while True:
            logger.info("Creating new GCN consumer...")
            streams = list(map(lambda s: s.name, GCNStream.objects.all())) + ["gcn.heartbeat"]

            consumer = Consumer(
                client_id="36drla0hks7njn1bkfhvir7iaq",
                client_secret="138mt2l6agb13cq0vli7g8v5rut6n18hmlr21u4r31hjbh5n5feg",
            )
            consumer.subscribe(streams)

            for _ in range(300):
                for message in consumer.consume(timeout=1):
                    if message.topic() == "gcn.heartbeat":
                        logger.debug(f"Recieved a new message ({message.topic()} #{message.offset()})")
                    else:
                        logger.info(f"Recieved a new message ({message.topic()} #{message.offset()})")

                    logger.debug(f"{message.value().decode()}")

                    if message.error():
                        logger.warning(message.error())
                    elif message.topic() == "gcn.heartbeat":
                        try:
                            t = dateutil.parser.parse(json.loads(message.value())["alert_datetime"])
                            cache.set("gcn_last_seen", t, timeout=None)
                        except Exception as e:
                            logger.error("An error occurred processing GCN heartbeat", exc_info=e)
                    else:
                        try:
                            stream = GCNStream.objects.get(name=message.topic())
                            notice = Notice(stream=stream, payload=message.value())
                            notice.full_clean()
                            notice.save()
                        except Exception as e:
                            logger.error("An error occurred saving a new notice:", exc_info=e)
