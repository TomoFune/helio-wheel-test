"""Find the most recent solar/lunar eclipse before a given moment, so
that moment's heliocentric chart can be shown as a "solar/lunar eclipse
chart" (spec extension, requested 2026-08-28: "1つ前の日食/月食の日の
ヘリオ図をすぐ出せたらいい").

This intentionally stays a *date-finding* tool, not a full eclipse
geometry model:

- Solar eclipse (new moon, Sun-Moon geocentric elongation = 0 deg) and
  lunar eclipse (full moon, elongation = 180 deg) are found by
  bisecting the Sun-Moon elongation for the exact syzygy time, walking
  backward from the given moment one synodic month at a time.
- Whether a given syzygy is *actually* an eclipse (as opposed to an
  ordinary new/full moon) is screened by checking the Moon's ecliptic
  latitude at that instant against an approximate threshold derived
  from the traditional eclipse-limit tables (Meeus, *Astronomical
  Algorithms*, ch. 54) -- not a full shadow/umbra-penumbra/visible-
  from-location model. This is enough to correctly identify "was there
  an eclipse on this date" for the ~4-7 eclipses/year that occur, but
  is not a substitute for a dedicated eclipse-prediction tool if exact
  magnitude, path, or local visibility is ever needed.
- Sun/Moon positions come from the same JPL DE440s kernel as the rest
  of this app (via astropy `get_body`, which includes light-time and
  aberration -- unlike the app's *heliocentric planet* calculation,
  which is deliberately geometric/uncorrected; the correction is
  negligible at the day-level precision this search needs, so using
  the simpler/more standard `get_body` here isn't a methodology
  inconsistency, just a different tool for a different sub-problem).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from astropy.coordinates import GeocentricTrueEcliptic, get_body
from astropy.time import Time, TimeDelta
import astropy.units as u

from .ephemeris import _ensure_ephemeris

# Traditional eclipse-limit tables express this as a maximum distance
# from the lunar node at syzygy; converted to the equivalent ecliptic-
# latitude-of-Moon-at-syzygy threshold used here. Solar limits are
# wider than lunar because the Sun's much larger apparent size (vs.
# Earth's shadow) makes grazing geometry more forgiving.
SOLAR_ECLIPSE_LATITUDE_LIMIT_DEG = 1.6
LUNAR_ECLIPSE_LATITUDE_LIMIT_DEG = 1.0

_SYNODIC_MONTH_DAYS = 29.530588853


@dataclass(frozen=True)
class EclipseEvent:
    time: Time
    kind: str  # "solar" or "lunar"
    moon_latitude_deg: float


def _sun_moon_elongation_and_moon_latitude(t: Time) -> tuple[float, float]:
    _ensure_ephemeris()
    sun = get_body("sun", t).transform_to(GeocentricTrueEcliptic(equinox=t))
    moon = get_body("moon", t).transform_to(GeocentricTrueEcliptic(equinox=t))
    elongation = (moon.lon.to(u.deg).value - sun.lon.to(u.deg).value) % 360.0
    return elongation, float(moon.lat.to(u.deg).value)


def _wrapped_phase_diff(elongation_deg: float, target_deg: float) -> float:
    """elongation - target, wrapped to (-180, 180] -- so a sign change
    means the elongation just crossed `target`."""
    return (elongation_deg - target_deg + 180.0) % 360.0 - 180.0


_COARSE_SCAN_DAYS = 35  # > one synodic month (29.53 days), same safety margin the old day-stepping loop used
_FINE_SCAN_POINTS = 96  # subdivides the ~1-day coarse bracket to ~15 min resolution


def _phase_diffs(times: Time, target_deg: float) -> np.ndarray:
    """Vectorized `_sun_moon_elongation_and_moon_latitude`'s elongation
    half, for an array of `times` in one batched astropy call. Batching
    matters a lot here: each individual `get_body()`/`transform_to()`
    call pays a fixed setup cost (ephemeris interpolation, frame-
    transform matrix construction) that dwarfs the actual per-point
    work, so evaluating N candidate times in one array call is roughly
    20x faster than N separate scalar calls (measured, 2026-09-10) --
    the difference between this search taking ~1s and ~3.7s in the
    browser (Pyodide/WASM) vs. tens of milliseconds."""
    _ensure_ephemeris()
    sun = get_body("sun", times).transform_to(GeocentricTrueEcliptic(equinox=times))
    moon = get_body("moon", times).transform_to(GeocentricTrueEcliptic(equinox=times))
    elongation = (moon.lon.to(u.deg).value - sun.lon.to(u.deg).value) % 360.0
    return _wrapped_phase_diff(elongation, target_deg)


def _first_crossing(times: Time, diffs: np.ndarray) -> tuple[Time, Time]:
    """First adjacent pair in `times`/`diffs` (in the order given) whose
    wrapped phase difference changes sign -- same real-crossing-vs-
    wraparound distinction the original loop made: a genuine root
    crossing moves by a few tens of degrees between adjacent samples,
    while a sign flip caused by the phase-diff's own +-180 deg
    wraparound (the *opposite* syzygy, half a synodic month away) jumps
    by ~347 deg instead."""
    for i in range(1, len(diffs)):
        f_near, f_far = diffs[i - 1], diffs[i]
        if (f_far < 0) != (f_near < 0) and abs(f_near - f_far) < 180.0:
            return times[i - 1], times[i]
    raise RuntimeError("could not bracket a syzygy within the scan window -- unexpected")


def _find_syzygy(t0: Time, target_deg: float, *, direction: int) -> Time:
    """Exact time of the nearest new-moon (target_deg=0) or full-moon
    (target_deg=180) syzygy strictly before (`direction=-1`) or after
    (`direction=+1`) `t0`. Two vectorized passes: a coarse 1-day-step
    scan (elongation advances ~13 deg/day, so a full synodic month --
    ~29.5 days -- is always enough to bracket exactly one crossing)
    finds the day it falls on, then a fine scan within that day narrows
    it to ~15-minute resolution -- far more precision than this app
    needs (heliocentric longitudes barely move minute to minute; the
    existing tests only check the calendar date), so no iterative
    bisection is needed at all."""
    coarse_offsets = np.arange(0, _COARSE_SCAN_DAYS + 1) * float(direction)
    coarse_times = t0 + TimeDelta(coarse_offsets, format="jd")
    coarse_diffs = _phase_diffs(coarse_times, target_deg)
    t_a, t_b = _first_crossing(coarse_times, coarse_diffs)
    t_lo, t_hi = (t_a, t_b) if t_a < t_b else (t_b, t_a)

    fine_offsets = np.linspace(0.0, 1.0, _FINE_SCAN_POINTS)
    fine_times = t_lo + TimeDelta(fine_offsets, format="jd")
    fine_diffs = _phase_diffs(fine_times, target_deg)
    t_a2, t_b2 = _first_crossing(fine_times, fine_diffs)
    return t_a2 + (t_b2 - t_a2) / 2


def _find_eclipse(t0: Time, kind: str, *, direction: int) -> EclipseEvent:
    if kind == "solar":
        target, limit = 0.0, SOLAR_ECLIPSE_LATITUDE_LIMIT_DEG
    elif kind == "lunar":
        target, limit = 180.0, LUNAR_ECLIPSE_LATITUDE_LIMIT_DEG
    else:
        raise ValueError(f"kind must be 'solar' or 'lunar', got {kind!r}")

    search_from = t0
    # Eclipses (solar or lunar) occur at least twice a year, so this
    # search window (~5 years of synodic months) is a generous margin,
    # not a tuned/fragile bound.
    for _ in range(65):
        syzygy_t = _find_syzygy(search_from, target, direction=direction)
        _, moon_lat = _sun_moon_elongation_and_moon_latitude(syzygy_t)
        if abs(moon_lat) <= limit:
            return EclipseEvent(time=syzygy_t, kind=kind, moon_latitude_deg=moon_lat)
        search_from = syzygy_t + TimeDelta(direction * 1.0, format="jd")
    raise RuntimeError(f"no {kind} eclipse found within the search window")


def find_previous_eclipse(t0: Time, kind: str) -> EclipseEvent:
    """The most recent solar (`kind="solar"`) or lunar (`kind="lunar"`)
    eclipse strictly before `t0`. Walks back through consecutive
    syzygies (skipping ordinary new/full moons that aren't eclipses)
    until the Moon-latitude screen passes."""
    return _find_eclipse(t0, kind, direction=-1)


def find_next_eclipse(t0: Time, kind: str) -> EclipseEvent:
    """The next solar (`kind="solar"`) or lunar (`kind="lunar"`) eclipse
    strictly after `t0` -- same search as `find_previous_eclipse`, just
    walking forward instead of backward (added 2026-09-05 so the UI's
    transit eclipse jump can step to either side of the current moment
    instead of only ever landing on a fixed pair of dates)."""
    return _find_eclipse(t0, kind, direction=1)
