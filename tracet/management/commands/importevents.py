"""
\\o events.txt
select xml_packet from trigger_app_event where xml_packet like '%SWIFT%' order by id desc limit 50000
"""

import logging
import urllib3

from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime
from lxml import etree

from tracet.models import Event, GCNStream


urllib3.disable_warnings()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        with open("events.txt") as f:
            lines = f.readlines()[4:-3]
            lines = list(map(lambda line: line.strip().strip("|").strip(), lines))

            # Valid xml must have a single root element
            lines.insert(0, "<TraceT>")
            lines.append("</TraceT>")

            blob = "".join(lines)

            events = etree.fromstring(blob).xpath("//TraceT/VOEvent")

            for event in events:
                ivorn = event.xpath("./@ivorn")[0]
                stream = ivorn.replace("ivo://nasa.gsfc.gcn/", "")

                # Remove random metadata appended to the ivorn, e.g. time, ids, etc.
                while stream[-1].isnumeric():
                    stream = "_".join(stream.split("_")[:-1])

                stream = stream.upper()
                stream = stream.replace("#", "_")

                mapper = {
                    "SWIFT_BAT_GRB_POS": "SWIFT_BAT_GRB_POS_ACK",  # ??
                    "SWIFT_BAT_GRB_TEST_POS": "SWIFT_BAT_GRB_POS_TEST",
                    "SWIFT_BAT_LIGHTCURVE": "SWIFT_BAT_GRB_LC",
                    "SWIFT_BAT_QUICKLOOK_POS": "SWIFT_BAT_QL_POS",
                    "SWIFT_BAT_TRANS_POS": "SWIFT_BAT_TRANS",
                    "SWIFT_POINT_DIR": "SWIFT_POINTDIR",
                    "SWIFT_ACTUAL_POINT_DIR": "SWIFT_ACTUAL_POINTDIR",
                    "SWIFT_XRT_PROC_SPER": "SWIFT_XRT_SPER_PROC",
                    "SWIFT_XRT_PROC_SPEC": "SWIFT_XRT_SPECTRUM_PROC",
                    "SWIFT_XRT_PROC_THRESHPIX": "SWIFT_XRT_THRESHPIX_PROC",
                    "SWIFT_UVOT_NACK_POS": "SWIFT_UVOT_POS_NACK",
                    "SWIFT_XRT_POS": "SWIFT_XRT_POSITION",
                    "SWIFT_XRT_SPEC": "SWIFT_XRT_SPECTRUM",
                    "SWIFT_XRT_LIGHTCURVE": "SWIFT_XRT_LC",
                    "SWIFT_XRT_NACK_POS": "SWIFT_XRT_POSITION",  # ??
                    "SWIFT_XRT_PROC_IMAGE": "SWIFT_XRT_IMAGE_PROC",
                }

                # I don't know how to map these to streams
                if (
                    stream
                    in (
                        "SWIFT_UVOT_IMAGE",
                        "SWIFT_UVOT_PROC_IMAGE",
                        "SWIFT_UVOT_SRCLIST",
                        "SWIFT_UVOT_PROC_SRCLIST",
                    )
                    or stream[:3] == "IVO"
                ):
                    continue

                stream = "gcn.classic.voevent." + mapper.get(stream, stream)

                time = event.xpath(
                    "./WhereWhen/ObsDataLocation/ObservationLocation/AstroCoords/Time/TimeInstant/ISOTime/text()"
                )

                try:
                    s = GCNStream.objects.get(name=stream)
                    e = Event(
                        stream=s,
                        created=parse_datetime(time[0]),
                        payload=etree.tostring(event, encoding="utf8"),
                    )
                    e.full_clean()
                    e.save()
                except Exception as e:
                    print(etree.tostring(event))
                    print(ivorn, "=>", stream)

                    raise Exception
                    # logger.warning("Failed to save event", exc_info=e)
