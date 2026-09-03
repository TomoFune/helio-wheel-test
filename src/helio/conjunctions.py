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

from .deep_sky import DEEP_SKY_OBJECTS, deep_sky_heliocentric_longitude
from .stars import STARS, star_heliocentric_longitude

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
    lon: float  # ordinary (non-rotated) heliocentric longitude of the reference point
    separation_deg: float


def find_conjunctions(
    body_longitudes: dict[str, float],
    t: Time,
    *,
    orb_deg: float = DEFAULT_ORB_DEG,
    include_stars: bool = True,
    include_deep_sky: bool = True,
) -> dict[str, list[ConjunctionHit]]:
    """For each body, every star/deep-sky object within `orb_deg`,
    closest first. Bodies with no hits are omitted from the result."""
    references: list[tuple[str, str, float, str]] = []
    if include_stars:
        for key, star in STARS.items():
            references.append((key, "star", star_heliocentric_longitude(key, t), star["label_ja"]))
    if include_deep_sky:
        for key, obj in DEEP_SKY_OBJECTS.items():
            references.append(
                (key, "deep_sky", deep_sky_heliocentric_longitude(key, t), obj["label_ja"])
            )

    result: dict[str, list[ConjunctionHit]] = {}
    for body_key, body_lon in body_longitudes.items():
        hits = [
            ConjunctionHit(ref_key, kind, label, ref_lon, sep)
            for ref_key, kind, ref_lon, label in references
            if (sep := angular_separation(body_lon, ref_lon)) <= orb_deg
        ]
        if hits:
            hits.sort(key=lambda h: h.separation_deg)
            result[body_key] = hits
    return result
