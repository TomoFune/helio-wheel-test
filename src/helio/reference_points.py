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


# 「恒星・銀河との合」の表示先を絞り込むための3分類のうち、GCS以外の2つ
# (2026-09-10、「恒星リスト選択はGCS/主要な恒星・銀河/その他の3分類」
# より) -- GCS(8つの起点候補)はJS側で既に別管理(GCS_STAR_KEYS)のため
# ここでは定義しない。「主要」はユーザー提供の2つの一覧(horoscopeheart.com
# のブレイディ恒星占星術64星、polock.s223.xrea.comの285星のうち太文字
# 85星)を突き合わせ、既存カタログに無かった分を追加した上でのキー一覧。
# 「その他」は元の一覧の残り約203星に相当するが、今回はスコープ外
# (JS側で「工事中」表示のプレースホルダーのみ)。
MAJOR_REFERENCE_KEYS: set[str] = {
    # 恒星
    "alderamin", "alpheratz", "alrescha", "mirach", "hamal", "schedar", "tsih",
    "menkar", "algol", "alcyone", "mirfak", "aldebaran", "rigel", "bellatrix",
    "capella", "phact", "mintaka", "elnath", "alnilam", "alnitak", "polaris",
    "betelgeuse", "menkalinan", "mirzam", "alhena", "sirius", "canopus", "castor",
    "pollux", "procyon", "acubens", "dubhe", "merak", "alphard", "regulus",
    "phecda", "megrez", "sex_principal", "thuban", "zosma", "denebola", "alkes",
    "diadem", "vindemiatrix", "gienah", "alchiba", "spica", "arcturus",
    "miaplacidus", "gacrux", "acrux", "alphecca", "zubenelgenubi",
    "zubeneschamali", "lup_principal", "hadar", "rigil_kentaurus", "antares",
    "rasalgethi", "sabik", "rasalhague", "nunki", "vega", "rukbat", "peacock",
    "albireo", "altair", "fawaris", "sualocin", "sadalsuud", "deneb_algedi",
    "sadr", "sadalmelik", "fomalhaut", "deneb", "achernar", "ankaa", "markab",
    "scheat", "quadrans",
    # 銀河・星団
    "andromeda_galaxy", "sunflower_galaxy", "galactic_center",
    "aculeus", "acumen", "facies", "capulus",
}


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
