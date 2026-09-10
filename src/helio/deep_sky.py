"""Deep-sky (galaxy / star cluster / nebula) reference points (spec
section 9).

These get the same "rotate the chart so this sits at 0 deg Aries"
treatment as a star (`stars.rotate_to_reference` is reused as-is), but
proper motion is intentionally *not* modeled: per spec, proper motion
of distant galaxies etc. is not worth accounting for at the timescale
of a human birth date, and most of these objects don't have a
meaningfully measurable one anyway.

Distance is set to a large fixed placeholder rather than sourced per
object: `HeliocentricMeanEcliptic` requires *some* finite distance to
do its Sun-ward origin shift, but for anything this far away the shift
is utterly negligible regardless of the exact real distance (a 1 AU
origin shift against hundreds to millions of parsecs moves the
resulting longitude by a small fraction of an arcsecond) -- so using
the object's real distance vs. a generic placeholder makes no visible
difference, and the placeholder avoids implying a precision this app
isn't actually sourcing.
"""
from __future__ import annotations

from astropy.coordinates import HeliocentricMeanEcliptic, SkyCoord
from astropy.time import Time
import astropy.units as u

# Arbitrary, but far larger than any real proper-motion or origin-shift
# effect could matter at ecliptic-longitude precision.
_PLACEHOLDER_DISTANCE = 1e6 * u.pc

DEEP_SKY_OBJECTS: dict[str, dict] = {
    "galactic_center": {
        "label_ja": "銀河系中心(いて座A*)",
        "name_en": "Sgr A* / Galactic Center",
        "kind": "galactic_center",
        "source": "SIMBAD (queried 2026-08-27), ICRS J2000",
        "ra_deg": 266.41681662499997,
        "dec_deg": -29.00782497222222,
    },
    "andromeda_galaxy": {
        "label_ja": "アンドロメダ銀河(M31)",
        "name_en": "M31 / Andromeda Galaxy",
        "kind": "galaxy",
        "source": "SIMBAD (queried 2026-08-27), ICRS J2000",
        "ra_deg": 10.684708333333333,
        "dec_deg": 41.268750000000004,
    },
    # --- expanded 2026-08-27 ---
    "whirlpool_galaxy": {
        "label_ja": "子持ち銀河(M51)",
        "name_en": "M51 / Whirlpool Galaxy",
        "kind": "galaxy",
        "source": "SIMBAD (queried 2026-08-27), ICRS J2000",
        "ra_deg": 202.469575,
        "dec_deg": 47.19525833333333,
    },
    "sombrero_galaxy": {
        "label_ja": "ソンブレロ銀河(M104)",
        "name_en": "M104 / Sombrero Galaxy",
        "kind": "galaxy",
        "source": "SIMBAD (queried 2026-08-27), ICRS J2000",
        "ra_deg": 189.99763274591663,
        "dec_deg": -11.623054494444448,
    },
    "large_magellanic_cloud": {
        "label_ja": "大マゼラン雲",
        "name_en": "Large Magellanic Cloud",
        "kind": "galaxy",
        "source": "SIMBAD (queried 2026-08-27), ICRS J2000",
        "ra_deg": 80.89416666666666,
        "dec_deg": -69.75611111111111,
    },
    "small_magellanic_cloud": {
        "label_ja": "小マゼラン雲",
        "name_en": "Small Magellanic Cloud",
        "kind": "galaxy",
        "source": "SIMBAD (queried 2026-08-27), ICRS J2000",
        "ra_deg": 13.158333333333333,
        "dec_deg": -72.80027777777778,
    },
    "pleiades": {
        "label_ja": "プレアデス星団(すばる/M45)",
        "name_en": "M45 / Pleiades",
        "kind": "cluster",
        "source": "SIMBAD (queried 2026-08-27), ICRS J2000",
        "ra_deg": 56.600833333333334,
        "dec_deg": 24.11388888888889,
    },
    "beehive_cluster": {
        "label_ja": "プレセペ星団(M44)",
        "name_en": "M44 / Beehive Cluster",
        "kind": "cluster",
        "source": "SIMBAD (queried 2026-08-27), ICRS J2000",
        "ra_deg": 130.05416666666665,
        "dec_deg": 19.62111111111111,
    },
    "hyades": {
        "label_ja": "ヒアデス星団",
        "name_en": "Hyades",
        "kind": "cluster",
        "source": "SIMBAD (queried 2026-08-27), ICRS J2000",
        "ra_deg": 67.44708333333334,
        "dec_deg": 16.948055555555555,
    },
    "orion_nebula": {
        "label_ja": "オリオン大星雲(M42)",
        "name_en": "M42 / Orion Nebula",
        "kind": "nebula",
        "source": "SIMBAD (queried 2026-08-27), ICRS J2000",
        "ra_deg": 83.8201,
        "dec_deg": -5.3876,
    },
    "crab_nebula": {
        "label_ja": "かに星雲(M1)",
        "name_en": "M1 / Crab Nebula",
        "kind": "nebula",
        "source": "SIMBAD (queried 2026-08-27), ICRS J2000",
        "ra_deg": 83.6324,
        "dec_deg": 22.0174,
    },
    "omega_centauri": {
        "label_ja": "オメガ星団(ケンタウルス座)",
        "name_en": "Omega Centauri / NGC 5139",
        "kind": "cluster",
        "source": "SIMBAD (queried 2026-08-27), ICRS J2000",
        "ra_deg": 201.69699999999997,
        "dec_deg": -47.47947222222223,
    },
    "sunflower_galaxy": {
        "label_ja": "ひまわり銀河(M63)",
        "name_en": "M63 / Sunflower Galaxy",
        "kind": "galaxy",
        "source": "SIMBAD basic data (queried 2026-09-10), ICRS",
        "ra_deg": 198.95530912246997,
        "dec_deg": 42.02936891003,
    },
    # --- 2026-09-10、恒星占星術で使われる4つの星団(アキュレウス/アキュメン
    # /ファシーズ/カプルス、polock.s223.xrea.comの恒星リストより)を追加。
    # 個々の星ではなく星団そのものなので、既存のプレアデス星団等と同じ
    # "cluster"扱いにした。
    "aculeus": {
        "label_ja": "アキュレウス(M6)",
        "name_en": "M6 / Butterfly Cluster",
        "kind": "cluster",
        "source": "SIMBAD basic data (queried 2026-09-10), ICRS",
        "ra_deg": 265.06916666666666,
        "dec_deg": -32.24194444444445,
    },
    "acumen": {
        "label_ja": "アキュメン(M7)",
        "name_en": "M7 / Ptolemy Cluster",
        "kind": "cluster",
        "source": "SIMBAD basic data (queried 2026-09-10), ICRS",
        "ra_deg": 268.44708333333335,
        "dec_deg": -34.84111111111112,
    },
    "facies": {
        "label_ja": "ファシーズ(M22)",
        "name_en": "M22 / Sagittarius Cluster",
        "kind": "cluster",
        "source": "SIMBAD basic data (queried 2026-09-10), ICRS",
        "ra_deg": 279.09975000000003,
        "dec_deg": -23.90475,
    },
    "capulus": {
        "label_ja": "カプルス(ペルセウス座二重星団)",
        "name_en": "Capulus / h+chi Persei Double Cluster",
        "kind": "cluster",
        # NGC 869(h Per)とNGC 884(chi Per)の中間点 -- 二重星団全体を
        # 1つの参照点として扱う(polockさんのリストでの扱いと同じ)。
        "source": "SIMBAD basic data (queried 2026-09-10), ICRS, midpoint of NGC 869/NGC 884",
        "ra_deg": 35.1625,
        "dec_deg": 57.14138889,
    },
}


def deep_sky_heliocentric_longitude(key: str, t: Time) -> float:
    obj = DEEP_SKY_OBJECTS[key]
    coord = SkyCoord(
        ra=obj["ra_deg"] * u.deg,
        dec=obj["dec_deg"] * u.deg,
        distance=_PLACEHOLDER_DISTANCE,
        frame="icrs",
    )
    result = coord.transform_to(HeliocentricMeanEcliptic(equinox=t, obstime=t))
    return float(result.lon.to(u.deg).value % 360.0)


def deep_sky_heliocentric_longitudes(
    t: Time, keys: list[str] | None = None
) -> dict[str, float]:
    """Vectorized (2026-09-10, same reasoning as stars.py's
    `stars_heliocentric_longitudes` -- one batched SkyCoord/transform_to
    call instead of one per object)."""
    objs = keys if keys is not None else list(DEEP_SKY_OBJECTS)
    if not objs:
        return {}
    coord = SkyCoord(
        ra=[DEEP_SKY_OBJECTS[k]["ra_deg"] for k in objs] * u.deg,
        dec=[DEEP_SKY_OBJECTS[k]["dec_deg"] for k in objs] * u.deg,
        distance=_PLACEHOLDER_DISTANCE,
        frame="icrs",
    )
    result = coord.transform_to(HeliocentricMeanEcliptic(equinox=t, obstime=t))
    lons = (result.lon.to(u.deg).value % 360.0).tolist()
    return dict(zip(objs, lons))


def search_deep_sky(query: str) -> list[str]:
    """Case-insensitive substring search over Japanese and English name."""
    q = query.strip().lower()
    if not q:
        return []
    return [
        key
        for key, obj in DEEP_SKY_OBJECTS.items()
        if q in obj["label_ja"].lower() or q in obj["name_en"].lower()
    ]
