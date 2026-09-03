"""Global configuration for the heliocentric engine.

Import this module before touching astropy's solar_system_ephemeris —
it fixes a Windows-specific SSL issue (Python's default urllib context
can't find the system CA store here) and pins the ephemeris kernel.
"""
from __future__ import annotations

import os

import certifi

# Without this, astropy's first-time kernel download fails with
# CERTIFICATE_VERIFY_FAILED on this machine (Windows Python + urllib
# does not pick up the OS certificate store automatically).
os.environ.setdefault("SSL_CERT_FILE", certifi.where())

# DE440s: JPL public-domain numerical ephemeris, ~32 MB, valid 1849-2150.
# Covers essentially any realistic birth date. If a birth date falls
# outside that range, switch to "de440" (full range 1550-2650, ~114 MB).
EPHEMERIS_KERNEL = "de440s"

# Bodies computed for the "ordinary heliocentric" chart, in display order.
# The Sun is excluded (it is the origin, not a point in the chart).
PLANETS: list[str] = [
    "mercury",
    "venus",
    "earth",
    "mars",
    "jupiter",
    "saturn",
    "uranus",
    "neptune",
    "pluto",
]

PLANET_LABELS_JA: dict[str, str] = {
    "mercury": "水星",
    "venus": "金星",
    "earth": "地球",
    "mars": "火星",
    "jupiter": "木星",
    "saturn": "土星",
    "uranus": "天王星",
    "neptune": "海王星",
    "pluto": "冥王星",
}

# Standard Unicode astrological symbols. All 9 render correctly in
# "Meiryo" and "Segoe UI Symbol" on Windows (checked via font cmap
# inspection + visual comparison against both fonts, and cross-checked
# Jupiter specifically against Unicode's own glyph description -- ♃'s
# "stylized Z with a crossbar" look is correct, not a font bug, even
# though it doesn't resemble the more ornate glyph some people expect).
PLANET_SYMBOLS: dict[str, str] = {
    "mercury": "☿",
    "venus": "♀",
    "earth": "⊕",
    "mars": "♂",
    "jupiter": "♃",
    "saturn": "♄",
    "uranus": "♅",
    "neptune": "♆",
    "pluto": "♇",
}
