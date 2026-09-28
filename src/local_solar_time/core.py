"""Compute local apparent solar time from longitude and standard meridian.

Local apparent solar time is what a sundial reads. It differs from civil
"standard time" by two terms:

    LAST = standard_time + 4*(standard_meridian - longitude) + EOT

* 4*(standard_meridian - longitude) converts standard time to local *mean*
  solar time. Earth rotates 1° every 4 minutes.
* EOT (equation of time) corrects mean solar time for the Earth's orbital
  eccentricity and axial tilt, yielding *apparent* solar time.

The EOT model here is the four-harmonic approximation from Spencer (1971),
which is accurate to within ~30 seconds year-round. That is more than
sufficient for sundial calibration, building-orientation studies, and any
application where civil-second precision is not required.
"""

import math
from datetime import datetime, timedelta, timezone


class SolarCalculator:
    """Stateless helpers for the equation of time and solar geometry.

    Kept separate from :class:`LocalSolarTime` so callers who only need the
    equation of time (e.g. to annotate a plot) do not have to commit to a
    longitude or a standard meridian.
    """

    @staticmethod
    def day_of_year(dt: datetime) -> int:
        """Return 1-based day-of-year (Jan 1 = 1, Dec 31 = 365 or 366)."""
        return dt.timetuple().tm_yday

    @staticmethod
    def equation_of_time(dt: datetime) -> timedelta:
        """Return the equation of time for ``dt`` as a :class:`~datetime.timedelta`.

        Positive means the sun is ahead of mean solar time (sundial fast),
        negative means behind. The sign convention follows the common
        sundial literature: LAST = standard_time + offset + EOT.

        Uses Spencer's four-harmonic Fourier fit in the day angle
        ``B = 2π * (n - 1) / 365``. Spencer (1971) reports the residual
        against astronomical ephemerides as under 30 s; we re-derive the
        coefficients from that source rather than fitting our own because
        the fit is already good enough and the coefficients are public.
        """
        n = dt.timetuple().tm_yday
        B = 2.0 * math.pi * (n - 1) / 365.0
        # Coefficients from Spencer (1971), "Fourier Series Representation
        # of the Position of the Sun". Units: minutes.
        eot_min = (
            229.18 * (
                0.0000075
                + 0.001868 * math.cos(B)
                - 0.032077 * math.sin(B)
                - 0.014615 * math.cos(2 * B)
                - 0.040849 * math.sin(2 * B)
            )
        )
        return timedelta(minutes=eot_min)

    @staticmethod
    def solar_declination(dt: datetime) -> float:
        """Return solar declination in degrees for ``dt``.

        Included because most callers who need apparent solar time also need
        declination for zenith/azimuth work. Uses the standard single-harmonic
        approximation; error is under ~1.5° vs. NOAA high-precision tables,
        adequate for non-navigational use.
        """
        n = dt.timetuple().tm_yday
        B = 2.0 * math.pi * (n - 1) / 365.0
        # Cooper's approximation (1969). Simple and widely cited.
        return 23.45 * math.sin(math.radians(360 * (284 + n) / 365))


class LocalSolarTime:
    """Convert civil wall-clock time to local apparent solar time.

    Parameters
    ----------    longitude_deg
        Observer longitude in decimal degrees, east positive.
    standard_meridian_deg
        Longitude of the standard-time meridian the input clock follows.
        For UTC this is 0. For US Eastern it is -75. For Central European
        Time it is +15. If omitted, defaults to 0 (i.e. the input is UTC).
    clock
        Optional callable returning a timezone-aware ``datetime``. Injected
        so tests can drive the "current time" deterministically. Defaults
        to :func:`datetime.now` (UTC).

    Notes
    -----
    The input datetime is interpreted as civil standard time at
    ``standard_meridian_deg``. If a naive datetime is passed to :meth:`now`,
    it is assumed to already be in that standard time. We do not attempt
    DST handling: callers in DST regions should pass standard time or
    subtract the DST offset before calling.
    """

    def __init__(
        self,
        longitude_deg: float,
        standard_meridian_deg: float = 0.0,
        clock=None,
    ):
        if not math.isfinite(longitude_deg):
            raise ValueError("longitude_deg must be finite")
        if not math.isfinite(standard_meridian_deg):
            raise ValueError("standard_meridian_deg must be finite")
        if not -180.0 <= longitude_deg <= 180.0:
            raise ValueError(
                f"longitude_deg must be in [-180, 180], got {longitude_deg}"
            )
        if not -180.0 <= standard_meridian_deg <= 180.0:
            raise ValueError(
                "standard_meridian_deg must be in [-180, 180], "
                f"got {standard_meridian_deg}"
            )
        self.longitude_deg = float(longitude_deg)
        self.standard_meridian_deg = float(standard_meridian_deg)
        self._clock = clock if clock is not None else lambda: datetime.now(timezone.utc)

    @property
    def longitudinal_offset(self) -> timedelta:
        """Mean-solar correction: 4 min per degree of (meridian - longitude).

        East of the standard meridian the sun transits earlier, so apparent
        solar time is ahead; the sign works out so that adding this offset to
        standard time yields local mean solar time.
        """
        minutes = 4.0 * (self.standard_meridian_deg - self.longitude_deg)
        return timedelta(minutes=minutes)

    def to_solar(self, standard_time: datetime) -> datetime:
        """Convert a civil standard time to local apparent solar time.

        The date and the seconds-fraction are preserved; only the offset and
        equation of time are applied. If ``standard_time`` is timezone-aware
        the result is timezone-aware with the same tzinfo.
        """
        eot = SolarCalculator.equation_of_time(standard_time)
        return standard_time + self.longitudinal_offset + eot

    def now(self) -> datetime:
        """Return local apparent solar time at the injected clock's current moment."""
        return self.to_solar(self._clock())
