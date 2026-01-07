import io
import logging
import urllib3

from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime
from lxml import etree
import requests

from tracet.models import Event, GCNStream


urllib3.disable_warnings()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        for id in range(570000, 705065):
            r = requests.get(
                f"https://tracet.duckdns.org/voevent_view/{id}/", verify=False
            )
            if r.status_code == requests.codes.ok:
                b = io.BytesIO(r.content)
                tree = etree.parse(b)
                time = tree.xpath(
                    "//WhereWhen/ObsDataLocation/ObservationLocation/AstroCoords/Time/TimeInstant/ISOTime/text()"
                )
                ivorn = tree.xpath("//@ivorn")

                if len(time) and len(ivorn) and "SWIFT" in ivorn[0]:
                    ivorn = ivorn[0].lstrip("ivo://nasa.gsfc.gcn/")
                    ivorn = ivorn.replace("#", "_")
                    ivorn = "_".join(ivorn.split("_")[0:-2])
                    stream = "gcn.classic.voevent." + ivorn.upper()
                    print(id)
                    print(parse_datetime(time[0]))
                    print(stream)

                    stream = stream.replace("POINT_DIR", "POINTDIR")
                    stream = stream.replace(
                        "SWIFT_BAT_GRB_TEST", "SWIFT_BAT_GRB_POS_TEST"
                    )
                    stream = stream.replace("SWIFT_BAT_QUICKLOOK", "SWIFT_BAT_QL_POS")
                    stream = stream.replace("SWIFT_FOM", "SWIFT_FOM_OBS")
                    stream = stream.replace("SWIFT_SC", "SWIFT_SC_SLEW")
                    stream = stream.replace("SWIFT_XRT", "SWIFT_XRT_POSITION")

                    if stream == "gcn.classic.voevent.SWIFT_UVOT":
                        stream = "gcn.classic.voevent.SWIFT_UVOT_POS"

                    # stream = stream.replace("SWIFT_XRT_PROC", "SWIFT_XRT_IMAGE_PROC")
                    if stream in (
                        "gcn.classic.voevent.SWIFT_BAT",
                        "gcn.classic.voevent.SWIFT_BAT_GRB",
                    ):
                        stream = "gcn.classic.voevent.SWIFT_BAT_GRB_LC"

                    try:
                        s = GCNStream.objects.get(name=stream)
                        e = Event(
                            stream=s, created=parse_datetime(time[0]), payload=r.content
                        )
                        e.full_clean()
                        e.save()
                    except Exception as e:
                        logger.warning("Failed to save event", exc_info=e)
