import datetime
import json
import logging

from astropy.coordinates import SkyCoord
import requests

from django.db import models

from TraceT2App.models import Event, Observation, Trigger


logger = logging.getLogger(__name__)


class MWA(models.Model):
    OBSERVATORY = "MWA"

    trigger = models.OneToOneField(
        Trigger, related_name="%(class)s", on_delete=models.CASCADE
    )

    projectid = models.CharField(max_length=500)
    password = models.CharField(max_length=500)
    repointing_threshold = models.FloatField()
    frequency = models.CharField(
        max_length=500,
        help_text=(
            "A space separated list of MWA coarse channel specifications. The specification format "
            "is documented <a href='https://mwatelescope.atlassian.net/wiki/spaces/MP/pages/24972656/Triggering+web+services#Channel-selection-specifier-strings'>here.</a> "
            "For example: '145,24' will observe with 24 channels centered at channel 145; a space "
            "separated list like '121:24 145:160;165:170' will schedule two separate observations."
        ),
    )
    frequency_resolution = models.FloatField(
        default=10, help_text="Correlator frequency resolution. [kHz]"
    )
    time_resolution = models.FloatField(
        default=0.5, help_text="Correlator integration time. [second]"
    )
    exposure = models.FloatField(
        default=120,
        help_text="The duration of each observation (for each frequency range). [second]",
    )  # TODO: validate as modulo 8 second
    nobs = models.IntegerField(
        default=15,
        help_text="The total number of observations. The total time will equal: (nobs) * (number of frequency ranges) * (exposure time)",
    )
    maximum_window = models.IntegerField(
        help_text=(
            "The maximum window of time following an event in which observations maybe be "
            "scheduled. Observations will may be truncated to not exceed this window, and "
            "events occurring after this window will be ignored. [second]"
        )
    )
    # tileset = [all_on, phase_one, p1+hexes, p1+solar, p2_compact, p2_extended, 256T]

    def __str__(self):
        return "MWA Configuration"

    def schedulenow(self, event: Event):
        try:
            ra = event.querylatest(self.trigger.ra_path)
            dec = event.querylatest(self.trigger.dec_path)

            ra, dec = float(ra), float(dec)
        except Exception as e:
            logger.error("An error occurred attempting to parse Ra,Dec values", exc_info=e)
            return False

        istest = not self.trigger.active

        params = dict(
            project_id=self.projectid,
            secure_key=self.password,
            calibrator=True,  # CHECK
            ra=ra,
            dec=dec,
            avoidsun=True,  # CHECK
            freqspecs=json.dumps(self.frequency.split()),
            pretend=istest,
        )

        try:
            response = requests.get(
                "http://mro.mwa128t.org/trigger/triggerobs", params=params
            )
            response.raise_for_status()

            success = json.loads(response.text).get("success", False)
            log = response.text
        except Exception as e:
            logger.error("An error occurred triggering an MWA observation", exc_info=e)
            success = False
            log = str(e)

        finish = (
            datetime.datetime.now(datetime.UTC) +
            datetime.timedelta(
                seconds=self.nobs * len(self.frequency.split()) * self.exposure + 120  # 120 is the default calibration time
            )
        )

        observation = Observation(
            trigger=self.trigger,
            event=event,
            observatory=self.OBSERVATORY,
            priority=self.trigger.priority,
            success=success,
            istest=istest,
            finish=finish,
            log=log,
        )
        observation.save()

        return observation
