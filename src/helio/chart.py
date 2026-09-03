"""Circular chart rendering (Phase 7 + the natal/transit/biwheel
extension the user asked for afterward): a single wheel (ordinary or a
chosen reference point's rotated frame -- spec section 14, never overlay
two *reference points* on one wheel) that can show one time (natal
alone, or transit alone) or two times at once as a biwheel (natal ring
inside, transit ring outside -- this is a second, independent kind of
overlay from the reference-point one: two *times*, one reference point).

Static PNG output via matplotlib. This proves the layout/legend logic
works for the immediate personal-use case; it is not the final PWA
renderer (see README "Open architecture question" -- Astropy/matplotlib
don't run in-browser, so the actual chart-drawing code will likely be
rewritten in JS/canvas or SVG once the platform question is settled).

Layout convention (this one **is** a user-specified requirement, not a
stylistic default -- see `SCREEN_ROTATION_OFFSET_DEG` in `_xy()`):
longitude increasing counter-clockwise, rotated so Aries sits where a
naive clockwise-from-12-o'clock layout would have put Sagittarius, and
Cancer sits where that layout would have put Virgo.

Biwheel reference-star epoch choice: when a star/galaxy reference point
is used, its own heliocentric longitude drifts slowly over time
(precession, ~50 arcsec/year, plus its own proper motion). For a
biwheel this app evaluates the reference point **once, at the natal
epoch**, and uses that single shift for both rings -- matching standard
astrological practice where a transit chart is overlaid onto the
natal chart's own fixed zodiacal frame rather than each moment getting
its own re-zeroed frame. (This was an explicitly open question in the
project's own notes; documented here now that it's been decided.)
"""
from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Circle, Wedge

from .config import PLANET_SYMBOLS
from .degrees import SIGNS, format_astrological, longitude_to_sign_position
from .minor_bodies import MINOR_BODIES, SEGOE_FALLBACK_FONT_KEYS

# Meiryo has full glyph coverage for both Japanese text AND the classic
# zodiac + 9-planet Unicode astrological symbols (verified via font cmap
# inspection -- Yu Gothic, used originally, is missing all of them).
matplotlib.rcParams["font.family"] = "Meiryo"

BODY_SYMBOLS: dict[str, str] = {
    **PLANET_SYMBOLS,
    **{key: obj["symbol"] for key, obj in MINOR_BODIES.items() if obj["symbol"]},
    # lilith_asteroid has no symbol (see minor_bodies.py) -- plain
    # katakana marker instead, consistent with the legend fallback below.
    "lilith_asteroid": "リ",
}

# Meiryo doesn't have the asteroid/Chiron/Eris glyphs (see minor_bodies.py);
# Segoe UI Symbol does. These are drawn with an explicit font override
# rather than a font.family fallback list, since matplotlib doesn't do
# per-glyph fallback within one font family string -- a missing glyph
# just renders as a blank/placeholder box, it doesn't skip to the next
# font in the list.
_NEEDS_SEGOE_FONT = SEGOE_FALLBACK_FONT_KEYS
_SEGOE_SYMBOL_FONT = FontProperties(family="Segoe UI Symbol")

# The side legend is one multi-line ax.text call per column (for layout
# simplicity), which can only use one font -- so a Segoe-only glyph can't
# be mixed in there the way it can on the wheel (where each marker gets
# its own ax.text call and can carry its own fontproperties). These
# short Japanese labels stand in for the legend specifically; the wheel
# markers themselves still show the real Unicode symbol.
_LEGEND_TEXT_FALLBACK: dict[str, str] = {
    "ceres": "穀", "pallas": "パ", "juno": "ジ", "vesta": "ベ", "chiron": "キ", "eris": "エ",
}


def _legend_marker(key: str, marker_map: dict[str, str]) -> str:
    if key in _NEEDS_SEGOE_FONT:
        return _LEGEND_TEXT_FALLBACK.get(key, key[:2])
    return marker_map.get(key, key[:2])


def _degree_minute_label(lon_deg: float) -> str:
    """e.g. "♈3°35'" -- degree+minute only (no seconds), for the compact
    inline label placed just outside the wheel next to each body."""
    p = longitude_to_sign_position(lon_deg)
    return f"{p.sign_symbol}{p.raw_degree_in_sign}°{p.minute:02d}'"

_SIGN_WEDGE_COLORS = ["#f5f5f5", "#e8e8e8"]
_TRANSIT_COLOR = "#3b7dd8"


SCREEN_ROTATION_OFFSET_DEG = 270.0


def _xy(lon_deg: float, radius: float) -> tuple[float, float]:
    """Ecliptic longitude -> screen position. Counter-clockwise, with
    the offset set so Aries lands where Sagittarius used to sit and
    Cancer lands where Virgo used to sit (this exact placement is a
    user-specified requirement, not a stylistic default -- see chart.py
    git history / project notes for the two reference points used to
    derive `SCREEN_ROTATION_OFFSET_DEG`)."""
    theta = math.radians((SCREEN_ROTATION_OFFSET_DEG - lon_deg) % 360.0)
    return radius * math.sin(theta), radius * math.cos(theta)


def _stagger_radii(
    longitudes: dict[str, float], base_radius: float, step: float, cluster_gap_deg: float = 8.0
) -> dict[str, float]:
    """When several bodies land close together in longitude, their
    markers/labels overlap. Group bodies whose consecutive gap (by
    longitude, wrapping around 0/360) is under `cluster_gap_deg` and
    stagger each cluster inward one `step` at a time, so a tight knot
    of planets fans out into a readable stack instead of a single
    illegible blob."""
    keys = sorted(longitudes, key=lambda k: longitudes[k])
    n = len(keys)
    if n == 0:
        return {}

    gaps = [
        (longitudes[keys[(i + 1) % n]] - longitudes[keys[i]]) % 360.0 for i in range(n)
    ]
    # Start the walk right after the single largest gap, so a cluster
    # that straddles the 0/360 wrap isn't artificially split in two.
    cut = max(range(n), key=lambda i: gaps[i])
    order = [keys[(cut + 1 + i) % n] for i in range(n)]

    radii: dict[str, float] = {}
    depth = 0
    for i, key in enumerate(order):
        if i > 0:
            prev_key = order[i - 1]
            gap = (longitudes[key] - longitudes[prev_key]) % 360.0
            depth = depth + 1 if gap < cluster_gap_deg else 0
        radii[key] = max(base_radius - depth * step, step * 1.5)
    return radii


def _draw_body_ring(
    ax,
    longitudes: dict[str, float],
    *,
    marker_map: dict[str, str],
    base_radius: float,
    step: float,
    outer_boundary: float,
    text_color: str,
    degree_labels: bool = False,
    degree_label_base_radius: float = 0.40,
    degree_label_step: float = 0.08,
) -> dict[str, float]:
    """Draws one ring of body markers + radial guide lines; returns the
    per-body radius actually used (so callers can position related
    annotations, e.g. conjunction markers, consistently).

    `degree_labels=True` additionally prints each body's degree+minute
    just inside the marker ring, toward the center (own stagger band,
    same clustering logic as the markers, just a smaller base radius so
    it doesn't collide with them) -- **not outside the wheel**: that was
    tried first, but the user found it collided with the fixed-star/
    deep-sky conjunction markers (also drawn near the wheel edge),
    making both hard to read together."""
    radii = _stagger_radii(longitudes, base_radius=base_radius, step=step)
    if degree_labels:
        label_radii = _stagger_radii(longitudes, base_radius=degree_label_base_radius, step=degree_label_step)
    for key, lon in longitudes.items():
        r = radii[key]
        label = marker_map.get(key, key[:2])
        x, y = _xy(lon, r)
        # Bare symbol, no circle background -- a circled glyph reads as
        # harder to make out than the plain symbol the user's geocentric
        # chart uses, and it's not the convention most astrology software
        # follows either.
        text_kwargs = {"fontproperties": _SEGOE_SYMBOL_FONT} if key in _NEEDS_SEGOE_FONT else {}
        ax.text(x, y, label, ha="center", va="center", fontsize=17, color=text_color, zorder=4, **text_kwargs)
        x_ring, y_ring = _xy(lon, outer_boundary)
        x_out, y_out = _xy(lon, r + 0.045)
        ax.plot([x_ring, x_out], [y_ring, y_out], color="#bbbbbb", linewidth=0.5, zorder=1)

        if degree_labels:
            lr = label_radii[key]
            lx, ly = _xy(lon, lr)
            ax.text(lx, ly, _degree_minute_label(lon), ha="center", va="center",
                    fontsize=12, color=text_color, zorder=4)
            xt_ring, yt_ring = _xy(lon, r - 0.05)
            xt_out, yt_out = _xy(lon, lr + 0.05)
            ax.plot([xt_ring, xt_out], [yt_ring, yt_out], color="#bbbbbb", linewidth=0.5, zorder=1)
    return radii


def render_chart(
    longitudes: dict[str, float],
    *,
    title: str,
    footer_lines: list[str],
    out_path: str | Path,
    markers: dict[str, str] | None = None,
    conjunction_markers: list[dict] | None = None,
    transit_longitudes: dict[str, float] | None = None,
    natal_label: str = "ネイタル",
    transit_label: str = "トランジット",
) -> None:
    """`longitudes`: body_key -> longitude in the frame to display
    (already rotated to a reference point if applicable -- this
    function just draws whatever it's given). `markers` overrides the
    default single-character label per body_key.

    `conjunction_markers`, if given: a list of dicts, each with `lon`
    (already rotated the same way as `longitudes`), `label_ja`,
    `kind` ("star" or "deep_sky"), `body_key`, and `separation_deg" --
    drawn as small star/diamond glyphs near the (natal-ring) body
    they're conjunct, with a legend section listing which body pairs
    with what.

    `transit_longitudes`, if given, draws a second ring (blue-outlined
    markers) outside the main one -- a biwheel. `longitudes` (still the
    natal data) becomes the inner ring in that case."""
    marker_map = dict(BODY_SYMBOLS)
    if markers:
        marker_map.update(markers)

    is_biwheel = transit_longitudes is not None

    # Figure size/extent scale with how much legend/conjunction content
    # there'll be, so a long list doesn't run off the edge of a
    # fixed-size figure -- happened in testing at various points.
    # `INCH_PER_UNIT` is an arbitrary but fixed scale (inches of figure
    # per data unit); the empirical per-line-height constants below are
    # calibrated against it, so if this changes, those need re-checking
    # against a rendered chart.
    #
    # Degree labels live inside the wheel now (own stagger band, smaller
    # radius than the marker ring -- see `_draw_body_ring`), not outside
    # it, so the wheel itself never exceeds `outer_r` regardless of
    # clustering; `wheel_half` only needs to fit the plain wheel.
    INCH_PER_UNIT = 3.088
    wheel_half = 1.15
    legend_fontsize, legend_line_unit = 15, 0.115
    conj_fontsize, conj_line_unit = 12, 0.10
    legend_col_width = 1.75

    legend_col_len = max(len(longitudes), len(transit_longitudes or {})) + (1 if is_biwheel else 0)
    conj_len = (len(conjunction_markers) + 1) if conjunction_markers else 0
    content_units = legend_col_len * legend_line_unit + conj_len * conj_line_unit + 0.5

    ylim_top = wheel_half + 0.15
    ylim_bottom = min(-wheel_half, ylim_top - content_units - 0.9)  # 0.9 ~ footer allowance
    fig_height = (ylim_top - ylim_bottom) * INCH_PER_UNIT

    legend_start_x = wheel_half + 0.15
    xlim_max = legend_start_x + (legend_col_width * 2 if is_biwheel else legend_col_width) + 0.15
    xlim_min = -wheel_half
    fig_width = (xlim_max - xlim_min) * INCH_PER_UNIT

    fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=150)
    ax.set_xlim(xlim_min, xlim_max)
    ax.set_ylim(ylim_bottom, ylim_top)
    ax.set_aspect("equal")
    ax.axis("off")

    outer_r = 1.0
    sign_ring_inner = 0.86
    tick_ring = 0.86

    # sign wedges -- zodiac symbol only, matching how a body marker shows
    # just its symbol with no separate text label; Meiryo covers all 12
    # zodiac glyphs natively. Wedge angles (matplotlib's own CCW-from-
    # east convention) are derived from the same lon->screen mapping
    # _xy() uses, via phi = (lon - 180) -- keeping this in sync with
    # _xy() is required, they're the same rotation expressed two ways
    # (one for point positions via sin/cos, one for the Wedge patch's
    # native angle parameters).
    for i, (_name_ja, _name_en, symbol) in enumerate(SIGNS):
        start = 30 * i - 180
        end = start + 30
        wedge = Wedge(
            (0, 0), outer_r, start, end,
            width=outer_r - sign_ring_inner,
            facecolor=_SIGN_WEDGE_COLORS[i % 2], edgecolor="#999999", linewidth=0.6,
        )
        ax.add_patch(wedge)
        mid_lon = i * 30 + 15
        sx, sy = _xy(mid_lon, (outer_r + sign_ring_inner) / 2)
        ax.text(sx, sy, symbol, ha="center", va="center", fontsize=15, color="#333333")

    ax.add_patch(Circle((0, 0), outer_r, fill=False, edgecolor="#333333", linewidth=1.2))
    ax.add_patch(Circle((0, 0), sign_ring_inner, fill=False, edgecolor="#999999", linewidth=0.6))

    # degree ticks every 10 deg, sign boundaries every 30 deg emphasized
    for d in range(0, 360, 10):
        r0 = tick_ring
        r1 = tick_ring - (0.03 if d % 30 == 0 else 0.015)
        x0, y0 = _xy(d, r0)
        x1, y1 = _xy(d, r1)
        ax.plot([x0, x1], [y0, y1], color="#666666", linewidth=0.8 if d % 30 == 0 else 0.4)

    # bodies -- markers only on the wheel (radius staggered so a tight
    # longitude cluster fans out into distinguishable positions instead
    # of stacking into one blob). Each body's exact degree+minute is
    # printed just outside the wheel too (also stagger-fanned for a
    # cluster), in addition to the full-precision side legend -- degrees
    # right next to the symbol is faster to read at a glance than
    # cross-referencing the legend, per the user's request; the legend
    # stays for full seconds-level precision and copy/paste-able text.
    # Only the natal/single ring gets outside labels -- adding them for
    # the transit ring too (in biwheel mode) would need guide lines
    # crossing back out through the natal ring and signs, which is
    # cluttered enough that it isn't worth it.
    #
    # Natal is the inner ring, transit the outer one (per user
    # instruction -- natal is the fixed/foundational chart, transiting
    # bodies pass around/outside it). No outside degree labels at all in
    # biwheel mode -- full precision is already in the legend, and the
    # user found on-wheel degree text unnecessary there once both rings'
    # legend columns are visible side by side.
    if is_biwheel:
        divider_r = 0.56
        ax.add_patch(Circle((0, 0), divider_r, fill=False, edgecolor="#aaaaaa", linewidth=0.6, linestyle="--"))
        _draw_body_ring(
            ax, transit_longitudes, marker_map=marker_map, base_radius=0.70, step=0.08,
            outer_boundary=sign_ring_inner, text_color=_TRANSIT_COLOR,
        )
        natal_radii = _draw_body_ring(
            ax, longitudes, marker_map=marker_map, base_radius=0.44, step=0.065,
            outer_boundary=divider_r, text_color="#000000",
        )
        conj_base_radius = max(natal_radii.values(), default=0.44)
    else:
        natal_radii = _draw_body_ring(
            ax, longitudes, marker_map=marker_map, base_radius=0.66, step=0.11,
            outer_boundary=sign_ring_inner, text_color="#000000", degree_labels=True,
        )
        conj_base_radius = 0.66

    # fixed-star / deep-sky conjunction markers -- drawn just outside the
    # natal ring, at their own (very close, by definition of "within
    # orb") longitude, with a distinct glyph so they read as "something
    # else is here" rather than another planet.
    for cm in conjunction_markers or []:
        r = conj_base_radius + 0.16
        x, y = _xy(cm["lon"], r)
        if cm["kind"] == "star":
            ax.scatter([x], [y], marker="*", s=170, color="#c9a227", edgecolor="#333333", linewidths=0.5, zorder=5)
        else:
            ax.scatter([x], [y], marker="D", s=70, color="#7a4fa3", edgecolor="#333333", linewidths=0.5, zorder=5)

    legend_top = ylim_top - 0.15
    title_x_frac = (0 - xlim_min) / (xlim_max - xlim_min)  # center title over the wheel, not the whole figure
    ax.set_title(title, fontsize=15, pad=14, x=title_x_frac)

    # side legend, in wheel longitude order. Biwheel uses two side-by-side
    # columns (natal / transit) rather than one long stacked list -- with
    # both lists (and minor bodies) that single-column list got long
    # enough to run off the bottom of the figure in testing.
    legend_keys = sorted(longitudes, key=lambda k: longitudes[k])
    legend_lines = [
        f"{_legend_marker(k, marker_map)}  {format_astrological(longitudes[k], use_symbol=True)}"
        for k in legend_keys
    ]
    # NB: no family="monospace" here -- the legend text mixes Japanese-
    # font-only glyphs (zodiac symbols) with regular characters, and the
    # default monospace font has neither (silently renders as tofu
    # boxes). Use the Meiryo default instead.
    if is_biwheel:
        transit_keys = sorted(transit_longitudes, key=lambda k: transit_longitudes[k])
        transit_lines = [
            f"{_legend_marker(k, marker_map)}  {format_astrological(transit_longitudes[k], use_symbol=True)}"
            for k in transit_keys
        ]
        ax.text(legend_start_x, legend_top, f"◯ {natal_label}\n" + "\n".join(legend_lines), ha="left", va="top",
                fontsize=legend_fontsize, color="#222222", linespacing=1.6)
        ax.text(legend_start_x + legend_col_width, legend_top, f"◯ {transit_label}\n" + "\n".join(transit_lines),
                ha="left", va="top", fontsize=legend_fontsize, color=_TRANSIT_COLOR, linespacing=1.6)
        legend_col_len = max(len(legend_lines), len(transit_lines)) + 1
    else:
        ax.text(legend_start_x, legend_top, "\n".join(legend_lines), ha="left", va="top",
                fontsize=legend_fontsize, color="#222222", linespacing=1.6)
        legend_col_len = len(legend_lines)

    if conjunction_markers:
        conj_lines = ["--- 恒星・銀河との合(ネイタル) ---"] + [
            f"{_legend_marker(cm['body_key'], marker_map)} × {cm['label_ja']}"
            f" ({cm['separation_deg']:.2f}°)"
            for cm in sorted(conjunction_markers, key=lambda c: c["separation_deg"])
        ]
        # Empirical per-line spacing in data units for this figure/fontsize
        # combination (verified by inspecting a rendered chart) -- not a
        # precise font-metrics conversion, just enough to clear the legend
        # above it without the two blocks overlapping.
        legend_gap = legend_col_len * legend_line_unit + 0.15
        ax.text(
            legend_start_x, legend_top - legend_gap, "\n".join(conj_lines), ha="left", va="top",
            fontsize=conj_fontsize, color="#5a3d80", linespacing=1.5,
        )

    footer_text = "\n".join(footer_lines)
    ax.text(
        0, ylim_bottom + 0.08, footer_text, ha="center", va="top", fontsize=7.5,
        color="#444444", family="monospace",
    )

    fig.tight_layout()
    fig.savefig(out_path, facecolor="white")
    plt.close(fig)


def _ordinary_longitudes(t, include_minor: bool) -> dict[str, float]:
    from .ephemeris import heliocentric_longitudes
    from .minor_bodies import minor_body_heliocentric_longitudes

    longitudes = heliocentric_longitudes(t)
    if include_minor:
        longitudes.update(minor_body_heliocentric_longitudes(t))
    return longitudes


def render_single_chart(
    resolved,
    *,
    star_key: str | None,
    out_path: str | Path,
    include_minor: bool = False,
    show_conjunctions: bool = False,
    conjunction_orb_deg: float = 1.0,
    conjunction_only: set[str] | None = None,
    label: str = "Birth",
    label_ja: str = "ネイタル",
) -> None:
    """One wheel for one moment -- used for both natal-alone and
    transit-alone (they're the same computation, just a different
    `resolved` time and footer label). `resolved` is a
    `time_resolve.ResolvedBirthTime`."""
    from . import config
    from .conjunctions import find_conjunctions
    from .reference_points import reference_info, resolve_reference_longitude
    from .stars import rotate_to_reference

    longitudes = _ordinary_longitudes(resolved.time, include_minor)

    # Conjunction search runs on the ordinary (pre-rotation) longitudes --
    # angular separation is invariant under the shared-shift rotation used
    # below, so it doesn't matter that this happens before the star-frame
    # rotation is applied.
    conjunction_markers: list[dict] = []
    if show_conjunctions:
        hits_by_body = find_conjunctions(longitudes, resolved.time, orb_deg=conjunction_orb_deg)
        for body_key, hits in hits_by_body.items():
            for hit in hits:
                if conjunction_only is not None and hit.ref_key not in conjunction_only:
                    continue
                conjunction_markers.append({
                    "lon": hit.lon,
                    "label_ja": hit.label_ja,
                    "kind": hit.ref_kind,
                    "ref_key": hit.ref_key,
                    "body_key": body_key,
                    "separation_deg": hit.separation_deg,
                })

    footer = [
        f"{label}: {resolved.local_dt.isoformat()} ({resolved.tz_name}) / UTC {resolved.utc_dt.isoformat()}",
        f"Planetary data: NASA/JPL {config.EPHEMERIS_KERNEL}",
    ]
    if show_conjunctions:
        footer.append(f"Fixed-star/deep-sky conjunction orb: {conjunction_orb_deg:.2f} deg")

    if star_key:
        star_lon = resolve_reference_longitude(star_key, resolved.time)
        star = reference_info(star_key)
        title = f"ヘリオセントリック・チャート ({label_ja} / {star['label_ja']}起点)"
        footer.insert(0, f"Reference: {star['name_en']} = Aries 0deg00'00\" (source: {star['source']})")
        footer.append("Stellar data: ESA/Hipparcos (van Leeuwen 2007)")
        shift = star_lon
    else:
        title = f"ヘリオセントリック・チャート ({label_ja}/通常)"
        shift = 0.0

    longitudes = {k: rotate_to_reference(v, shift) for k, v in longitudes.items()}
    for cm in conjunction_markers:
        cm["lon"] = rotate_to_reference(cm["lon"], shift)

    render_chart(
        longitudes, title=title, footer_lines=footer, out_path=out_path,
        conjunction_markers=conjunction_markers,
    )


# Kept as the pre-existing name so nothing else has to change; natal is
# just the "Birth" case of the same single-wheel renderer.
def render_birth_chart(resolved, **kwargs) -> None:
    kwargs.setdefault("label", "Birth")
    kwargs.setdefault("label_ja", "ネイタル")
    render_single_chart(resolved, **kwargs)


def render_biwheel_chart(
    natal_resolved,
    transit_resolved,
    *,
    star_key: str | None,
    out_path: str | Path,
    include_minor: bool = False,
) -> None:
    """Natal ring (inner) + transit ring (outer), same reference frame
    for both. The reference star/point's own longitude is evaluated
    once at the *natal* epoch and reused for the transit ring too --
    see this module's docstring for why.

    No fixed-star/deep-sky conjunction markers here (unlike the
    single-wheel renderer) -- the user found them too cluttered
    combined with an already-two-ring chart, so biwheel intentionally
    doesn't offer that option."""
    from . import config
    from .reference_points import reference_info, resolve_reference_longitude
    from .stars import rotate_to_reference

    natal_longitudes = _ordinary_longitudes(natal_resolved.time, include_minor)
    transit_longitudes = _ordinary_longitudes(transit_resolved.time, include_minor)

    footer = [
        f"Natal: {natal_resolved.local_dt.isoformat()} ({natal_resolved.tz_name}) / UTC {natal_resolved.utc_dt.isoformat()}",
        f"Transit: {transit_resolved.local_dt.isoformat()} ({transit_resolved.tz_name}) / UTC {transit_resolved.utc_dt.isoformat()}",
        f"Planetary data: NASA/JPL {config.EPHEMERIS_KERNEL}",
    ]

    if star_key:
        # Evaluated once, at the natal epoch -- shared by both rings.
        star_lon = resolve_reference_longitude(star_key, natal_resolved.time)
        star = reference_info(star_key)
        title = f"ヘリオセントリック・二重円 ({star['label_ja']}起点)"
        footer.insert(0, f"Reference: {star['name_en']} = Aries 0deg00'00\" at natal epoch (source: {star['source']})")
        footer.append("Stellar data: ESA/Hipparcos (van Leeuwen 2007)")
        shift = star_lon
    else:
        title = "ヘリオセントリック・二重円(通常)"
        shift = 0.0

    natal_longitudes = {k: rotate_to_reference(v, shift) for k, v in natal_longitudes.items()}
    transit_longitudes = {k: rotate_to_reference(v, shift) for k, v in transit_longitudes.items()}

    # Legend headers carry each ring's actual date/time -- without this,
    # a saved biwheel PNG only says "Natal" / "Transit" with nothing
    # distinguishing *which* natal or *which* transit moment it's for.
    natal_label = f"ネイタル ({natal_resolved.local_dt.strftime('%Y-%m-%d %H:%M')})"
    transit_label = f"トランジット ({transit_resolved.local_dt.strftime('%Y-%m-%d %H:%M')})"

    render_chart(
        natal_longitudes, title=title, footer_lines=footer, out_path=out_path,
        transit_longitudes=transit_longitudes, natal_label=natal_label, transit_label=transit_label,
    )
