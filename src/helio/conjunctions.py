"""Fixed-star / deep-sky "conjunction" detection: which catalog stars
or deep-sky objects fall within a chosen orb of a chart's body
positions.

Detection runs on *ordinary* (non-reference-rotated) heliocentric
longitudes. Angular separation between two points is invariant under
the "subtract a shared reference longitude" rotation used elsewhere in
this app -- rotating both operands by the same amount doesn't change
their difference -- so which conjunctions exist doesn't depend on which
reference star the chart is currently displayed relative to. Callers
that need the rotated display position for a hit can rotate `lon`
themselves with `stars.rotate_to_reference`.

Generic over what "body_longitudes" contains -- takes any {key: lon}
mapping, so it works the same way for a natal chart or a future transit
chart; no transit-specific code needed here when that gets built.
"""
from __future__ import annotations

from dataclasses import dataclass

from astropy.time import Time

from .deep_sky import DEEP_SKY_OBJECTS, deep_sky_heliocentric_longitudes
from .stars import STARS, stars_heliocentric_longitudes

DEFAULT_ORB_DEG = 1.0


def angular_separation(a: float, b: float) -> float:
    """Shortest angular distance between two longitudes, in [0, 180]."""
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


@dataclass(frozen=True)
class ConjunctionHit:
    ref_key: str
    ref_kind: str  # "star" or "deep_sky"
    label_ja: str
    constellation_ja: str  # "" for deep-sky objects (no constellation field)
    lon: float  # ordinary (non-rotated) heliocentric longitude of the reference point
    separation_deg: float


def find_conjunctions(
    body_longitudes: dict[str, float],
    t: Time,
    *,
    orb_deg: float = DEFAULT_ORB_DEG,
    include_stars: bool = True,
    include_deep_sky: bool = True,
    keys: list[str] | None = None,
) -> dict[str, list[ConjunctionHit]]:
    """For each body, every star/deep-sky object within `orb_deg`,
    closest first. Bodies with no hits are omitted from the result.

    `keys`, if given, restricts the search to exactly that set of
    STARS/DEEP_SKY_OBJECTS keys (e.g. a UI's "GCS only" or "主要な恒星
    ・銀河" selection, 2026-09-10) -- `include_stars`/`include_deep_sky`
    still apply on top of it (both default True, so passing `keys`
    alone is enough for the common case).

    Longitudes are computed in two batched calls (one for stars, one for
    deep-sky objects) rather than one per reference point -- ~90 stars
    one at a time measured ~800ms even natively (worse in the browser's
    Pyodide/WASM); batched, well under 100ms (2026-09-10, same lesson as
    today's eclipse-search speedup)."""
    star_keys = [k for k in STARS if keys is None or k in keys] if include_stars else []
    deep_sky_keys = [k for k in DEEP_SKY_OBJECTS if keys is None or k in keys] if include_deep_sky else []
    star_lons = stars_heliocentric_longitudes(star_keys, t)
    deep_sky_lons = deep_sky_heliocentric_longitudes(t, deep_sky_keys)

    references: list[tuple[str, str, float, str, str]] = [
        (key, "star", star_lons[key], STARS[key]["label_ja"], STARS[key]["constellation_ja"])
        for key in star_keys
    ] + [
        (key, "deep_sky", deep_sky_lons[key], DEEP_SKY_OBJECTS[key]["label_ja"], "")
        for key in deep_sky_keys
    ]

    result: dict[str, list[ConjunctionHit]] = {}
    for body_key, body_lon in body_longitudes.items():
        hits = [
            ConjunctionHit(ref_key, kind, label, const_ja, ref_lon, sep)
            for ref_key, kind, ref_lon, label, const_ja in references
            if (sep := angular_separation(body_lon, ref_lon)) <= orb_deg
        ]
        if hits:
            hits.sort(key=lambda h: h.separation_deg)
            result[body_key] = hits
    return result
