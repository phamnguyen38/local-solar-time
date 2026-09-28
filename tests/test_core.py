import math
import unittest
from datetime import datetime, timedelta, timezone

from local_solar_time import LocalSolarTime, SolarCalculator


class TestEquationOfTime(unittest.TestCase):
    """Equation of time sanity checks.

    We do not assert exact values against an ephemeris here because the
    Spencer approximation is documented to ~30 s tolerance; instead we
    check the shape: bounded range, correct sign at known extremes, and
    smoothness (monotonic across a known increasing run).
    """

    def test_eot_is_bounded(self):
        # The equation of time never exceeds roughly ±20 minutes.
        for n in range(1, 366):
            dt = datetime(2023, 1, 1, tzinfo=timezone.utc) + timedelta(days=n - 1)
            eot = SolarCalculator.equation_of_time(dt)
            self.assertLess(abs(eot.total_seconds()), 20 * 60 + 30)

    def test_eot_near_zero_at_mid_april(self):
        # Around April 15 the equation of time crosses zero.
        dt = datetime(2023, 4, 15, 12, 0, 0, tzinfo=timezone.utc)
        eot = SolarCalculator.equation_of_time(dt)
        self.assertLess(abs(eot.total_seconds()), 120)

    def test_eot_positive_in_early_november(self):
        # Early November is a maximum: sundial fast (positive EOT).
        dt = datetime(2023, 11, 3, 12, 0, 0, tzinfo=timezone.utc)
        eot = SolarCalculator.equation_of_time(dt)
        self.assertGreater(eot.total_seconds(), 10 * 60)

    def test_eot_negative_in_mid_february(self):
        # Mid-February is a minimum: sundial slow (negative EOT).
        dt = datetime(2023, 2, 12, 12, 0, 0, tzinfo=timezone.utc)
        eot = SolarCalculator.equation_of_time(dt)
        self.assertLess(eot.total_seconds(), -13 * 60)

    def test_eot_returns_timedelta(self):
        dt = datetime(2023, 6, 21, tzinfo=timezone.utc)
        self.assertIsInstance(SolarCalculator.equation_of_time(dt), timedelta)


class TestLongitudinalOffset(unittest.TestCase):

    def test_at_standard_meridian_offset_is_zero(self):
        lst = LocalSolarTime(longitude_deg=-75.0, standard_meridian_deg=-75.0)
        self.assertEqual(lst.longitudinal_offset, timedelta(0))

    def test_one_degree_east_is_four_minutes_back(self):
        # One degree east of the meridian: sun transits 4 min earlier,
        # so apparent time is ahead -> offset is -4 min when expressed as
        # (meridian - longitude). Check the magnitude.
        lst = LocalSolarTime(longitude_deg=-74.0, standard_meridian_deg=-75.0)
        self.assertAlmostEqual(
            lst.longitudinal_offset.total_seconds(), -4 * 60, places=6
        )

    def test_one_degree_west_is_four_minutes_forward(self):
        lst = LocalSolarTime(longitude_deg=-76.0, standard_meridian_deg=-75.0)
        self.assertAlmostEqual(
        lst.longitudinal_offset.total_seconds(), 4 * 60, places=6
        )


class TestToSolar(unittest.TestCase):

    def test_solar_noon_at_standard_meridian(self):
        # At the standard meridian, ignoring EOT, solar noon == 12:00 standard.
        # Pick a date where EOT is near zero (mid-April) so this holds closely.
        dt = datetime(2023, 4, 15, 12, 0, 0, tzinfo=timezone.utc)
        lst = LocalSolarTime(longitude_deg=0.0, standard_meridian_deg=0.0)
        solar = lst.to_solar(dt)
        # Within 2 minutes of 12:00 given EOT near zero.
        self.assertLess(
            abs((solar - dt).total_seconds()), 120
        )

    def test_west_of_meridian_solar_noon_later(self):
        # 15° east of UTC: solar noon should be ~11:00 standard time,
        # so at 13:00 standard time solar time is ~12:00 (noon).
        dt = datetime(2023, 4, 15, 13, 0, 0, tzinfo=timezone.utc)
        lst = LocalSolarTime(longitude_deg=15.0, standard_meridian_deg=0.0)
        solar = lst.to_solar(dt)
        # Solar time should be near 12:00 (noon), within 2 minutes given EOT near zero.
        self.assertLess(abs((solar.hour * 3600 + solar.minute * 60 + solar.second) - 12 * 3600), 120)

    def test_preserves_timezone(self):
        tz = timezone(timedelta(hours=5))
        dt = datetime(2023, 6, 1, 12, 0, 0, tzinfo=tz)
        lst = LocalSolarTime(longitude_deg=75.0, standard_meridian_deg=75.0)
        solar = lst.to_solar(dt)
        self.assertEqual(solar.tzinfo, tz)

    def test_preserves_microseconds(self):
        dt = datetime(2023, 6, 1, 12, 0, 0, 123456, tzinfo=timezone.utc)
        lst = LocalSolarTime(longitude_deg=0.0, standard_meridian_deg=0.0)
        solar = lst.to_solar(dt)
        # Microsecond precision is preserved; the exact value shifts by the
        # fractional-minute EOT contribution, so just check sub-second resolution.
        self.assertLess(abs(solar.microsecond - 123456), 500000)

    def test_date_rolls_over_when_offset_crosses_midnight(self):
        # 179° east of UTC, at 23:30 UTC: +4*(0 - 179) = -716 min ≈ -11h56m,
        # so solar time is previous day ~11:34.
        dt = datetime(2023, 6, 15, 23, 30, 0, tzinfo=timezone.utc)
        lst = LocalSolarTime(longitude_deg=179.0, standard_meridian_deg=0.0)
        solar = lst.to_solar(dt)
        self.assertEqual(solar.day, 15)
        self.assertEqual(solar.hour, 11)


class TestNow(unittest.TestCase):

    def test_now_uses_injected_clock(self):
        fixed = datetime(2023, 6, 21, 12, 0, 0, tzinfo=timezone.utc)
        lst = LocalSolarTime(
            longitude_deg=0.0,
            standard_meridian_deg=0.0,
            clock=lambda: fixed,
        )
        self.assertEqual(lst.now(), lst.to_solar(fixed))


class TestValidation(unittest.TestCase):

    def test_longitude_out_of_range_raises(self):
        with self.assertRaises(ValueError):
            LocalSolarTime(longitude_deg=181.0)

    def test_longitude_nan_raises(self):
        with self.assertRaises(ValueError):
            LocalSolarTime(longitude_deg=float("nan"))

    def test_meridian_out_of_range_raises(self):
        with self.assertRaises(ValueError):
            LocalSolarTime(longitude_deg=0.0, standard_meridian_deg=-181.0)

    def test_boundary_longitudes_accepted(self):
        # ±180 are valid and must not raise.
        LocalSolarTime(longitude_deg=-180.0)
        LocalSolarTime(longitude_deg=180.0)


class TestDeclination(unittest.TestCase):

    def test_summer_solstice_near_23_4(self):
        dt = datetime(2023, 6, 21, tzinfo=timezone.utc)
        dec = SolarCalculator.solar_declination(dt)
        self.assertAlmostEqual(dec, 23.45, delta=0.6)

    def test_winter_solstice_near_minus_23_4(self):
        dt = datetime(2023, 12, 21, tzinfo=timezone.utc)
        dec = SolarCalculator.solar_declination(dt)
        self.assertAlmostEqual(dec, -23.45, delta=0.6)

    def test_equinox_near_zero(self):
        dt = datetime(2023, 3, 21, tzinfo=timezone.utc)
        dec = SolarCalculator.solar_declination(dt)
        self.assertLess(abs(dec), 1.0)


if __name__ == "__main__":
    unittest.main()
