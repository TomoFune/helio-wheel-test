"""Ordinary (non-reference-shifted) heliocentric planetary longitudes.

Method, in full (see README.md for the long-form writeup):

- Position source: JPL DE440s numerical ephemeris (public domain),
  queried through astropy's `solar_system_ephemeris` / `get_body_barycentric`.
- Frame: astropy's `HeliocentricMeanEcliptic(equinox=<birth time>,
  obstime=<birth time>)` -- origin at the Sun's center, x-axis toward
  the *mean* equinox of date, xy-plane the *mean* ecliptic of date
  (IAU 2006 precession, no nutation). Both `equinox` (plane orientation)
  and `obstime` (when the Sun's position is evaluated for the origin
  shift) must be set to the birth time -- `obstime` defaults to J2000
  if omitted, which silently evaluates the origin at the wrong epoch.
- Geometric, not apparent: `get_body_barycentric` returns the
  instantaneous position with no light-time or stellar-aberration
  correction applied. This matches the spec's "mean position, no
  annual aberration" requirement, and is *not* the convention used by
  most tropical astrology software (which uses apparent/true-equinox
  positions) -- expect a systematic few-arcsecond-to-few-arcminute
  offset when cross-checking against those tools. That offset is
  expected, not a bug; see README.md Phase 2 notes.
- Time scale: UTC input is converted to TT internally by astropy for
  the ephemeris lookup (`Time` objects carry the scale; we pass the
  `Time` straight through and let astropy/erfa handle TT/TDB).
"""
from __future__ import annotations

from astropy.coordinates import ICRS, HeliocentricMeanEcliptic, get_body_barycentric
from astropy.coordinates import solar_system_ephemeris
from astropy.time import Time
import astropy.units as u

from . import config

_ephemeris_ready = False


def _ensure_ephemeris() -> None:
    global _ephemeris_ready
    if not _ephemeris_ready:
        solar_system_ephemeris.set(config.EPHEMERIS_KERNEL)
        _ephemeris_ready = True


def heliocentric_longitude(body: str, t: Time) -> float:
    """Heliocentric mean-ecliptic-of-date longitude of `body`, in degrees [0, 360)."""
    _ensure_ephemeris()
    pos = get_body_barycentric(body, t)
    # Both `equinox` (plane orientation) and `obstime` (when the origin/
    # Sun position is evaluated) must be pinned to the birth time -- the
    # frame defaults `obstime` to J2000 if it's left unset, which silently
    # shifts the Sun to its J2000 position while still rotating to the
    # equinox-of-date plane, corrupting the longitude by however far the
    # Sun moved between J2000 and the birth time.
    coord = ICRS(pos).transform_to(HeliocentricMeanEcliptic(equinox=t, obstime=t))
    return float(coord.lon.to(u.deg).value % 360.0)


def heliocentric_longitudes(t: Time, planets: list[str] | None = None) -> dict[str, float]:
    """Heliocentric mean-ecliptic-of-date longitudes for a set of bodies."""
    _ensure_ephemeris()
    bodies = planets if planets is not None else config.PLANETS
    return {body: heliocentric_longitude(body, t) for body in bodies}
