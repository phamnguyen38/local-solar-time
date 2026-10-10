# local-solar-time

Compute local apparent solar time (what a sundial reads) from an observer's
longitude and the standard-time meridian their clock follows.

```python
from datetime import datetime, timezone
from local_solar_time import LocalSolarTime

# Observer in Boston (71.06° W) on US Eastern Standard Time (-75° meridian).
lst = LocalSolarTime(longitude_deg=-71.06, standard_meridian_deg=-75.0)

standard_time = datetime(2023, 6, 21, 12, 0, 0, tzinfo=timezone.utc)
solar_time = lst.to_solar(standard_time)
print(solar_time)  # 2023-06-21 11:47:54.8...+00:00

# Or "now", using an injectable clock:
lst = LocalSolarTime(-71.06, -75.0, clock=lambda: datetime.now(timezone.utc))
print(lst.now())
```

## Why this exists

Civil time is uniform; the sun is not. The gap between the two is the
*equation of time*, and it swings by about ±15 minutes across the year.
Anyone calibrating a sundial, sizing a window overhang, or reasoning about
historical timestamps needs to close that gap.

This library uses Spencer's four-harmonic Fourier approximation (1971) for
the equation of time and Cooper's single-harmonic fit for solar declination.
Both are closed-form and dependency-free. The trade-off is precision: EOT is
within ~30 s of high-precision ephemerides, and declination within ~1.5°.
That is fine for sundials and architecture; it is not fine for navigation.

## Edge cases you will hit

- **Daylight saving time is not handled.** Pass standard time, or subtract
  your DST offset before calling. Trying to infer DST from a timezone name
  would pull in the `zoneinfo` database and a political rules table, which
  breaks the zero-dependency constraint.
- **Naive datetimes** passed to `to_solar` are treated as already being in
  the standard time of `standard_meridian_deg`. The result is naive too.
- **Longitude ±180 are accepted**; the antimeridian is a valid place to
  observe from.

## Exports

- `LocalSolarTime(longitude_deg, standard_meridian_deg=0.0, clock=None)` —
  the converter. Methods: `.to_solar(standard_time)`, `.now()`, property
  `.longitudinal_offset`.
- `SolarCalculator` — static helpers: `.equation_of_time(dt)`,
  `.solar_declination(dt)`, `.day_of_year(dt)`.

## Design notes

The window stores values eagerly rather than keeping running aggregates. Running
sums drift with floating point over long streams, and recomputing from a small
buffer is cheap enough that the drift is not worth the speed.

## Limitations

Values are coerced to floats, so very large integers lose precision. If you need
exact integer aggregates over a window, this is the wrong tool.

