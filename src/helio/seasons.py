"""Find the nearest spring/autumn equinox or summer/winter solstice
before or after a given moment, so the UI's T(トランジット) jump can
land on any of the four the same way it already jumps to a solar/lunar
eclipse (2026-09-10, "四季図も、次の春分、夏至、秋分、冬至...と選択
できるとさらに最高" -- previously only a single hardcoded 夏至 date
was available).

Definition: the four cardinal points are where Earth's heliocentric
longitude (the same value this app already shows for Earth on every
chart, via `ephemeris.heliocentric_longitude`) crosses 180/270/0/90
degrees respectively -- equivalent to the traditional definition (the
Sun's apparent geocentric longitude crossing 0/90/180/270), just
rotated 180 degrees since heliocentric Earth and geocentric Sun point
in opposite directions. Verified against real 2026 solstice/equinox
dates (2026-09-10): summer solstice lands at exactly 270 deg, the
equinoxes within ~0.2 deg of 180/0 (that residual is real -- the
equinox is defined by the *tropical*, equinox-of-date frame, not a
perfectly fixed 180/0 split -- and is irrelevant at the day-level
precision this search needs).

Unlike eclipses.py's syzygy search, no "is this actually one" screening
step is needed here: Earth's heliocentric longitude advances smoothly
and monotonically (no retrograde-like reversal the way an inner/outer
planet's *geocentric* longitude can have), so every crossing of a
target degree *is* the season change by definition -- one crossing per
~91 days, always.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from astropy.coordinates import ICRS, HeliocentricMeanEcliptic, get_body_barycentric
from astropy.time import Time, TimeDelta
import astropy.units as u

from .ephemeris import _ensure_ephemeris

SEASON_TARGET_DEG = {
    "springEquinox": 180.0,
    "summerSolstice": 270.0,
    "autumnEquinox": 0.0,
    "winterSolstice": 90.0,
}

# A given target degree (e.g. "summer solstice") recurs once per full
# sidereal year (~365.25 days), not once per season -- unlike eclipses,
# which recur roughly every synodic month, this window has to cover a
# whole year with margin so a search starting anywhere (including right
# at a crossing) can always find the *other* occurrence in the
# requested direction.
_COARSE_SCAN_DAYS = 370
_FINE_SCAN_POINTS = 96  # ~15 min resolution within the bracketed day, plenty for this app's needs


@dataclass(frozen=True)
class SeasonEvent:
    time: Time
    season: str  # one of SEASON_TARGET_DEG's keys


def _wrapped_phase_diff(lon_deg, target_deg: float):
    return (lon_deg - target_deg + 180.0) % 360.0 - 180.0


def _earth_lon_array(times: Time) -> np.ndarray:
    """Vectorized `ephemeris.heliocentric_longitude("earth", t)` for an
    array of `times` in one batched astropy call -- same reasoning as
    eclipses.py's `_phase_diffs`: batching avoids paying the fixed
    per-call setup cost (ephemeris interpolation, frame-transform
    matrix construction) once per candidate time."""
    _ensure_ephemeris()
    pos = get_body_barycentric("earth", times)
    coord = ICRS(pos).transform_to(HeliocentricMeanEcliptic(equinox=times, obstime=times))
    return coord.lon.to(u.deg).value % 360.0


def _first_crossing(times: Time, diffs: np.ndarray) -> tuple[Time, Time]:
    for i in range(1, len(diffs)):
        f_near, f_far = diffs[i - 1], diffs[i]
        if (f_far < 0) != (f_near < 0) and abs(f_near - f_far) < 180.0:
            return times[i - 1], times[i]
    raise RuntimeError("could not bracket a season crossing within the scan window -- unexpected")


def _find_season_crossing(t0: Time, target_deg: float, *, direction: int) -> Time:
    coarse_offsets = np.arange(0, _COARSE_SCAN_DAYS + 1) * float(direction)
    coarse_times = t0 + TimeDelta(coarse_offsets, format="jd")
    coarse_diffs = _wrapped_phase_diff(_earth_lon_array(coarse_times), target_deg)
    t_a, t_b = _first_crossing(coarse_times, coarse_diffs)
    t_lo, t_hi = (t_a, t_b) if t_a < t_b else (t_b, t_a)

    fine_offsets = np.linspace(0.0, 1.0, _FINE_SCAN_POINTS)
    fine_times = t_lo + TimeDelta(fine_offsets, format="jd")
    fine_diffs = _wrapped_phase_diff(_earth_lon_array(fine_times), target_deg)
    t_a2, t_b2 = _first_crossing(fine_times, fine_diffs)
    return t_a2 + (t_b2 - t_a2) / 2


def _find_season(t0: Time, season: str, *, direction: int) -> SeasonEvent:
    if season not in SEASON_TARGET_DEG:
        raise ValueError(f"season must be one of {sorted(SEASON_TARGET_DEG)}, got {season!r}")
    t = _find_season_crossing(t0, SEASON_TARGET_DEG[season], direction=direction)
    return SeasonEvent(time=t, season=season)


def find_previous_season(t0: Time, season: str) -> SeasonEvent:
    """The most recent occurrence of `season` (one of "springEquinox",
    "summerSolstice", "autumnEquinox", "winterSolstice") strictly before `t0`."""
    return _find_season(t0, season, direction=-1)


def find_next_season(t0: Time, season: str) -> SeasonEvent:
    """The next occurrence of `season` strictly after `t0`."""
    return _find_season(t0, season, direction=1)
