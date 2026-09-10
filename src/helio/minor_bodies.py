"""Heliocentric longitudes for asteroids / dwarf planets / centaurs.

Unlike the major planets (`ephemeris.py`, backed by the locally cached
DE440s kernel), these bodies have no small, pre-bundled *kernel* -- JPL
Horizons' small-body SPK files use SPK segment "Type 21" (numerically
integrated trajectories), which `jplephem` (the only SPK reader usable
in Pyodide/WASM) cannot read (confirmed 2026-09-11: `ValueError:
jplephem has not yet learned how to compute positions from an ephemeris
segment with data type 21`). So instead of a kernel, `minor_bodies.bin`
(baked once offline by scratchpad/bake_minor_bodies.py, not part of the
app) holds a plain daily-sampled longitude lookup table per body,
covering the same 1849-2150 range as DE440s. `minor_body_heliocentric_longitudes_fast`
below reads it and linearly interpolates -- fully offline, no network,
same as the major planets. Validated 2026-09-11 against the live query
below: worst case (fastest-moving body, Vesta) ~0.00002 deg error from
daily-step interpolation, far under any precision this app needs.

The live single-body query (`minor_body_heliocentric_longitude`) is
kept as the independent, network-based reference implementation the
baked table was validated against -- same ICRS ->
HeliocentricMeanEcliptic(equinox=t, obstime=t) rotation, same units,
same longitude convention as `ephemeris.py`, so cross-checks stay
apples-to-apples.

Body list is intentionally a plain dict so new bodies can be added
without touching any other code -- just add an entry with the body's
JPL small-body designation (numbered bodies use "<number>;" to
disambiguate from major-body NAIF IDs, per Horizons convention). Adding
a body here also requires re-running bake_minor_bodies.py to include it
in minor_bodies.bin before it'll work through the fast/offline path.
"""
from __future__ import annotations

import struct

import numpy as np
from astropy.coordinates import ICRS, CartesianRepresentation, HeliocentricMeanEcliptic
from astropy.time import Time
from astroquery.jplhorizons import Horizons
import astropy.units as u

from . import config

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


_TABLE_MAGIC = b"HELIOMB1"
_TABLE_MAX_KEY_LEN = 16
_table_cache: dict | None = None


def _load_table() -> dict:
    """Lazily load+parse minor_bodies.bin (must match the format written
    by scratchpad/bake_minor_bodies.py), cached for the process lifetime
    -- the file is only actually read once."""
    global _table_cache
    if _table_cache is not None:
        return _table_cache

    with open(config.MINOR_BODIES_TABLE_PATH, "rb") as f:
        data = f.read()

    if data[:8] != _TABLE_MAGIC:
        raise ValueError(f"bad magic in minor-bodies table at {config.MINOR_BODIES_TABLE_PATH}")
    start_jd, step_days = struct.unpack_from("<dd", data, 8)
    n_days, n_bodies = struct.unpack_from("<II", data, 24)

    offset = 32
    keys = []
    for _ in range(n_bodies):
        raw = data[offset:offset + _TABLE_MAX_KEY_LEN]
        keys.append(raw.rstrip(b"\0").decode("ascii"))
        offset += _TABLE_MAX_KEY_LEN

    lons_by_key: dict[str, np.ndarray] = {}
    for key in keys:
        lons_by_key[key] = np.frombuffer(data, dtype="<f4", count=n_days, offset=offset)
        offset += n_days * 4

    _table_cache = {"start_jd": start_jd, "step_days": step_days, "n_days": n_days, "lons": lons_by_key}
    return _table_cache


def minor_body_heliocentric_longitudes_fast(
    t: Time, keys: list[str] | None = None
) -> dict[str, float]:
    """Same result as `minor_body_heliocentric_longitudes`, but from the
    baked offline table (minor_bodies.bin) instead of a live Horizons
    query -- no network needed, fast enough to call on every chart
    render. This is what the app actually uses; the live functions
    above are kept only as the independent reference this was validated
    against (see module docstring)."""
    table = _load_table()
    start_jd, step_days, n_days = table["start_jd"], table["step_days"], table["n_days"]

    # float(): t.jd can come back as a numpy scalar, which would silently
    # turn every value below (and the final dict this returns) into
    # numpy float64 -- json.dumps (used by every engine.js bridge that
    # calls this) rejects that with a non-obvious TypeError.
    idx_f = float((t.jd - start_jd) / step_days)
    if idx_f < 0 or idx_f > n_days - 1:
        raise ValueError(
            f"date (jd={t.jd}) is outside the minor-body ephemeris table's range "
            f"(jd {start_jd} .. {start_jd + step_days * (n_days - 1)})"
        )
    idx0 = int(idx_f)
    idx1 = min(idx0 + 1, n_days - 1)
    frac = idx_f - idx0

    target_keys = keys if keys is not None else list(MINOR_BODIES)
    result = {}
    for key in target_keys:
        arr = table["lons"][key]
        lon0, lon1 = float(arr[idx0]), float(arr[idx1])
        delta = lon1 - lon0
        if delta > 180:
            delta -= 360
        elif delta < -180:
            delta += 360
        result[key] = (lon0 + frac * delta) % 360.0
    return result
