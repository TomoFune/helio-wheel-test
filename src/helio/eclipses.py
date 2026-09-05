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


def _phase_diff_at(t: Time, target_deg: float) -> float:
    elongation, _ = _sun_moon_elongation_and_moon_latitude(t)
    return _wrapped_phase_diff(elongation, target_deg)


def _find_syzygy(t0: Time, target_deg: float, *, direction: int) -> Time:
    """Exact time of the nearest new-moon (target_deg=0) or full-moon
    (target_deg=180) syzygy strictly before (`direction=-1`) or after
    (`direction=+1`) `t0`. Brackets the sign change in the wrapped
    phase difference by stepping a day at a time in the given direction
    (elongation advances ~13 deg/day, so a full synodic month -- ~29.5
    days -- is always enough to bracket exactly one crossing), then
    bisects for the precise instant."""
    step = TimeDelta(direction * 1.0, format="jd")
    t_near = t0
    f_near = _phase_diff_at(t_near, target_deg)
    t_far = t_near
    f_far = f_near
    for _ in range(40):
        t_far = t_near + step
        f_far = _phase_diff_at(t_far, target_deg)
        # A real root crossing moves by ~13 deg/day (the daily
        # elongation rate); a sign flip caused by the phase-diff's own
        # +-180 deg wraparound (the *opposite* syzygy, half a synodic
        # month away) jumps by ~347 deg instead -- the `< 180` check
        # tells these apart so the wraparound isn't mistaken for the
        # target crossing.
        if (f_far < 0) != (f_near < 0) and abs(f_near - f_far) < 180.0:
            break
        t_near, f_near = t_far, f_far
    else:
        raise RuntimeError("could not bracket a syzygy within 40 days -- unexpected")

    t_lo, f_lo = (t_near, f_near) if direction > 0 else (t_far, f_far)
    t_hi, f_hi = (t_far, f_far) if direction > 0 else (t_near, f_near)
    for _ in range(40):
        mid = t_lo + (t_hi - t_lo) / 2
        f_mid = _phase_diff_at(mid, target_deg)
        if (f_lo < 0) == (f_mid < 0):
            t_lo, f_lo = mid, f_mid
        else:
            t_hi, f_hi = mid, f_mid
    return t_lo + (t_hi - t_lo) / 2


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
