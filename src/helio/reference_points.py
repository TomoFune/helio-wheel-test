"""Unified lookup across the three kinds of "rotate the chart to put
this at 0 deg Aries" reference point this app supports: an individual
catalog star (`stars.STARS`), a GCS group center (`stars.STAR_GROUPS`,
e.g. Orion's belt or the Big Dipper as a single averaged point), or a
deep-sky object (`deep_sky.DEEP_SKY_OBJECTS`, e.g. the Andromeda
Galaxy). Each namespace is small and hand-curated, so keys are assumed
not to collide across them; callers that previously only knew about
`STARS` (cli.py, chart.py, comparison.py) can swap in
`resolve_reference_longitude`/`all_reference_keys` to accept any of
the three without otherwise changing shape.
"""
from __future__ import annotations

from astropy.time import Time

from .deep_sky import DEEP_SKY_OBJECTS, deep_sky_heliocentric_longitude
from .stars import STAR_GROUPS, STARS, group_center_longitude, star_heliocentric_longitude


def all_reference_keys() -> list[str]:
    return sorted(set(STARS) | set(STAR_GROUPS) | set(DEEP_SKY_OBJECTS))


def reference_info(key: str) -> dict:
    """The underlying dict for `key`, whichever namespace it's from --
    all three carry at least `label_ja`/`name_en`/`source`."""
    if key in STARS:
        return STARS[key]
    if key in STAR_GROUPS:
        return STAR_GROUPS[key]
    if key in DEEP_SKY_OBJECTS:
        return DEEP_SKY_OBJECTS[key]
    raise KeyError(key)


def resolve_reference_longitude(key: str, t: Time) -> float:
    if key in STARS:
        return star_heliocentric_longitude(key, t)
    if key in STAR_GROUPS:
        return group_center_longitude(key, t)
    if key in DEEP_SKY_OBJECTS:
        return deep_sky_heliocentric_longitude(key, t)
    raise KeyError(key)
