import datetime
import json
import logging

from astropy.coordinates import SkyCoord
from astropy.units import hourangle
import requests

from django.db import models
from django.utils import timezone

from TraceT2App.models import Event, Trigger


logger = logging.getLogger(__name__)


class Observation(models.Model):
    trigger = models.ForeignKey(Trigger, null=True, on_delete=models.SET_NULL)
    event = models.ForeignKey(Event, null=True, on_delete=models.SET_NULL)
    start = models.DateTimeField(default=timezone.now)
    finish = models.DateTimeField()
    observatory = models.CharField(max_length=500)
    priority = models.IntegerField()
    success = models.BooleanField()
    istest = models.BooleanField()
    log = models.TextField()

    def __bool__(self):
        return self.success and not self.istest


class MWA(models.Model):
    class TileSet(models.TextChoices):
        PHASE_ONE = "phase_one", "Phase 1"
        P1_HEXES = "p1+hexes", "Phase 1 + Hexes"
        P1_SOLAR = "p1+solar", "Phase 1 + Solar"
        P2_COMPACT = "p2_compact", "Phase 2 Compact"
        P2_EXTENDED = "p2_extended", "Phase 2 Extended"
        T256 = "256T", "256 tiles"

    OBSERVATORY = "MWA"

    trigger = models.OneToOneField(
        Trigger, related_name="%(class)s", on_delete=models.CASCADE
    )

    projectid = models.CharField(max_length=500)
    secure_key = models.CharField(max_length=500)
    repointing_threshold = models.FloatField()
    tileset = models.CharField(
        choices=TileSet,
        help_text="Select the set of tiles to use for this observation. More tiles gives better sensitivity but at the expense of larger data requirements.",
    )
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

    def __str__(self):
        return "MWA Configuration"

    def schedulenow(self, event: Event):
        try:
            ra = event.querylatest(self.trigger.ra_path)
            dec = event.querylatest(self.trigger.dec_path)

            ra, dec = float(ra), float(dec)
        except Exception as e:
            logger.error(
                "An error occurred attempting to parse RA,Dec values", exc_info=e
            )
            return False

        istest = not self.trigger.active

        params = dict(
            project_id=self.projectid,
            secure_key=self.secure_key,
            calibrator=True,  # Hard-coded to always make a calibrator observation.
            ra=ra,
            dec=dec,
            avoidsun=True,  # Hard-coded to always place sun in null.
            freqspecs=json.dumps(self.frequency.split()),
            tileset=self.tileset,
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

        finish = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
            seconds=self.nobs * len(self.frequency.split()) * self.exposure
            + 120  # 120 is the default calibration time
        )

        return Observation.objects.create(
            trigger=self.trigger,
            event=event,
            observatory=self.OBSERVATORY,
            priority=self.trigger.priority,
            success=success,
            istest=istest,
            finish=finish,
            log=log,
        )


class ATCA(models.Model):
    OBSERVATORY = "ATCA"

    trigger = models.OneToOneField(
        Trigger, related_name="%(class)s", on_delete=models.CASCADE
    )
    projectid = models.CharField(max_length=500)
    http_username = models.CharField(max_length=500, verbose_name="HTTP Username")
    http_password = models.CharField(max_length=500, verbose_name="HTTP Password")
    email = models.EmailField(
        help_text="The email address that was supplied in the NAPA proposal."
    )
    authentication_token = models.CharField(max_length=500)
    maximum_lag = models.FloatField(
        help_text="The maximum delay allowed for scheduling this observation. If the observation cannot be scheduled to start within this time, it will not be scheduled at all. [minute]"
    )
    minimum_exposure = models.IntegerField(
        help_text="The minimum exposure time required for this trigger. The trigger will be rejected if ATCA cannot schedule a total exposure of at least this time. [minute]"
    )
    maximum_exposure = models.IntegerField(
        help_text="The maximum exposure time required for this trigger. [minute]"
    )

    def __str__(self):
        return "ATCA Configuration"

    def schedulenow(self, event: Event):
        def minutes_to_hms(minutes: float) -> str:
            h = int(minutes // 60)
            minutes -= h * 60

            m = int(minutes)
            minutes -= m

            s = int(minutes * 60)

            return f"{h:02d}:{m:02d}:{s:02d}"

        try:
            ra = event.querylatest(self.trigger.ra_path)
            dec = event.querylatest(self.trigger.dec_path)
            coord = SkyCoord(float(ra), float(dec), unit=("deg", "deg"))
        except Exception as e:
            logger.error(
                "An error occurred attempting to parse RA,Dec values", exc_info=e
            )
            return False

        istest = not self.trigger.active

        params = dict(
            email=self.email,
            authenticationToken=self.authentication_token,
            maximumLag=self.maximum_lag / 60,  # [minute] -> [hour]
        )

        if istest:
            params |= dict(
                test=istest,
                emailOnly=self.email,  # Send all emails only to this email address (test mode only)
                noTimeLimit=True,  # Assume that we can request an over-ride observation of any length (test mode only)
                noScoreLimit=True,  # Assume that we can over-ride any observation (test mode only)
            )

        request = dict(
            source="gamma ray burst",  # IS THIS ARBITRARY??
            project=self.projectid,
            minExposureLength=minutes_to_hms(self.minimum_exposure),
            maxExposureLength=minutes_to_hms(self.maximum_exposure),
            rightAscension=coord.ra.to_string(unit=hourangle, sep=":"),
            declination=coord.dec.to_string(sep=":"),
            scanType="Dwell",
        )

        for atcaband in self.atcaband_set.order_by("band"):
            request[atcaband.get_band_display()] = dict(
                use=True,
                exposureLength=atcaband.exposure,
                freq1=atcaband.freq1,
                freq2=atcaband.freq2,
            )

        # Request is passed as a JSON string
        params["request"] = json.dumps(request)

        print(params)

        response = requests.post(
            "https://www.narrabri.atnf.csiro.au/cgi-bin/obstools/rapid_response/rapid_response_service.py",
            params,
        )

        print(response)

        return False


class ATCABand(models.Model):
    class Bands(models.IntegerChoices):
        L3mm = 3, "3mm"
        L7mm = 7, "6mm"
        L15mm = 15, "15mm"
        L4cm = 40, "4cm"
        L16cm = 160, "16cm"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["atca", "band"], name="unique wavelength configuration"
            )
        ]

    atca = models.ForeignKey(ATCA, on_delete=models.CASCADE)
    band = models.IntegerField(choices=Bands)
    exposure = models.IntegerField(
        help_text="The exposure time of this reciever. Receivers will be continuously cycled up until the full scheduled slot is exhausted. [minute]"
    )
    freq1 = models.IntegerField(
        verbose_name="Frequency 1",
        help_text="Specify the central frequency for the first of the 2 GHz bands at which this receiver will observe. Note: the 16 cm reciever can only observe at 2100 MHz. [MHz]"
    )
    freq2 = models.IntegerField(
        verbose_name="Frequency 2",
        help_text="Specify the central frequency for the second of the 2 GHz bands at which this receiver will observe. Note: the 16 cm reciever can only observe at 2100 MHz. [MHz]"
    )
