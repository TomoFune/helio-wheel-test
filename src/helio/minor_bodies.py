"""Heliocentric longitudes for asteroids / dwarf planets / centaurs,
via live JPL Horizons queries.

Unlike the major planets (`ephemeris.py`, backed by the locally cached
DE440s kernel), these bodies have no small, pre-bundled kernel covering
all of them -- there is no "de440s.bsp equivalent" for an arbitrary list
of asteroids. So each call here queries JPL Horizons live for that
body's position relative to the solar system barycenter, at the exact
birth instant, in the same frame (ICRF, effectively ICRS) that
`get_body_barycentric` returns for the major planets. That keeps this
pipeline byte-for-byte consistent with `ephemeris.py` downstream:
same ICRS -> HeliocentricMeanEcliptic(equinox=t, obstime=t) rotation,
same units, same longitude convention.

Practical consequence: **these specific bodies require an internet
connection at calculation time** (the major planets stay fully offline
after the one-time DE440s download). If/when this app needs to run
fully offline (PWA phase), the fix is to generate a small per-body SPK
kernel once via Horizons' file-generation service and cache it locally
like de440s.bsp -- deferred until that's actually needed.

Body list is intentionally a plain dict so new bodies can be added
without touching any other code -- just add an entry with the body's
JPL small-body designation (numbered bodies use "<number>;" to
disambiguate from major-body NAIF IDs, per Horizons convention).
"""
from __future__ import annotations

from astropy.coordinates import ICRS, CartesianRepresentation, HeliocentricMeanEcliptic
from astropy.time import Time
from astroquery.jplhorizons import Horizons
import astropy.units as u

MINOR_BODIES: dict[str, dict[str, str]] = {
    "ceres": {"label_ja": "セレス", "horizons_id": "1;", "symbol": "⚳"},
    "pallas": {"label_ja": "パラス", "horizons_id": "2;", "symbol": "⚴"},
    "juno": {"label_ja": "ジュノー", "horizons_id": "3;", "symbol": "⚵"},
    "vesta": {"label_ja": "ベスタ", "horizons_id": "4;", "symbol": "⚶"},
    "chiron": {"label_ja": "キロン", "horizons_id": "2060;", "symbol": "⚷"},
    "eris": {"label_ja": "エリス", "horizons_id": "136199;", "symbol": "⯰"},
    # Asteroid 1181 Lilith -- a real minor planet, distinct from "Black
    # Moon Lilith" (the Moon's apogee point, a geocentric orbital-geometry
    # construct with no heliocentric equivalent; not implemented here).
    # No symbol: the one Unicode "Lilith" glyph (U+26B8) is explicitly
    # BLACK MOON LILITH, and using it here would misleadingly imply that
    # unrelated point.
    "lilith_asteroid": {"label_ja": "リリス(小惑星1181番)", "horizons_id": "1181;", "symbol": None},
}

# The symbols above (Ceres..Eris) aren't in "Meiryo" (this app's main
# chart font, which does cover the classic 9-planet + zodiac symbols) --
# checked via font cmap inspection. "Segoe UI Symbol" has them. Kept
# here rather than in chart.py since the CLI's text table wants the same
# symbols without importing matplotlib just for a font-name constant.
SEGOE_FALLBACK_FONT_KEYS = {"ceres", "pallas", "juno", "vesta", "chiron", "eris"}


def minor_body_heliocentric_longitude(key: str, t: Time) -> float:
    horizons_id = MINOR_BODIES[key]["horizons_id"]
    obj = Horizons(id=horizons_id, location="@0", epochs=t.jd, id_type="smallbody")
    # refplane="earth" is required: Horizons' default `.vectors()` output
    # is the J2000 *ecliptic* frame, not equatorial/ICRF. Silently feeding
    # that into ICRS (which expects equatorial input) mis-rotates the
    # result by an amount that depends on the target's sky position --
    # caught by cross-checking Earth's Horizons vector against DE440s.
    row = obj.vectors(refplane="earth")[0]

    pos = CartesianRepresentation(
        float(row["x"]) * u.AU, float(row["y"]) * u.AU, float(row["z"]) * u.AU
    )
    coord = ICRS(pos).transform_to(HeliocentricMeanEcliptic(equinox=t, obstime=t))
    return float(coord.lon.to(u.deg).value % 360.0)


def minor_body_heliocentric_longitudes(
    t: Time, keys: list[str] | None = None
) -> dict[str, float]:
    bodies = keys if keys is not None else list(MINOR_BODIES)
    return {key: minor_body_heliocentric_longitude(key, t) for key in bodies}
