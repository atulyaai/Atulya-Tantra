"""Bake the hologram as horizontal isolines cut from a parametric bust.

Usage: python webui/bake_hologram_mesh.py
Requires only NumPy. Writes webui/hologram-points.bin.

No footage, no photograph, no embedded image. Every number that shapes the
figure lives below as a tunable constant: the silhouette is a smooth curve
through control points fitted to the reference proportions, the face glow is an
ellipse, the chest veins are two bezier curves, and the colours are measured
shader values. Changing the look means changing a number, never re-measuring
a video frame -- which is the whole point, now that voice, HUD binding and the
rest of the build all sit on top of this file.

The output is the same 7-float record the renderer already reads -- x, y, z,
r, g, b, size -- so the renderer needs no changes at all.

Where the numbers came from (2026-10-07, kept so a retune starts from facts):
the PROFILE control points are the per-row silhouette half-widths measured off
the reference footage at 4.8s, thinned to one point per feature (crown tip,
temple max, ear bump, neck, trapezius flare, shoulder run-off). The CLOUD
colour is rgb (12,108,171) sampled off the loose dots at the reference's edge.
CYAN/GOLD/RIM are set for what they look like added together: a stroke is
built from sprites spaced POINT_STEP apart and CYAN_SIZE wide, so roughly four
of them land on every pixel and the values would clip to grey-white if they
were specified at face value.
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent / "hologram-points.bin"

# Silhouette half-width rx at height y, crown to run-off. Read top to bottom:
# the tip of the crown, the temple max, the ear bump at y~0.32, the long neck,
# the trapezius flare from y~-0.4, and the shoulders held past the frame bottom
# so the chest leaves view instead of ending on a hem (the renderer already
# fades the body out across y = -1.45..-1.2). A point every feature is enough:
# the Hermite curve below keeps it C1 smooth between them, and adding points
# only ever sharpens a wiggle.
PROFILE = [
    (0.788, 0.000),
    (0.764, 0.076),
    (0.739, 0.101),
    (0.714, 0.126),
    (0.689, 0.178),
    (0.665, 0.185),
    (0.640, 0.210),
    (0.615, 0.229),
    (0.591, 0.261),
    (0.566, 0.239),
    (0.541, 0.270),
    (0.516, 0.316),
    (0.492, 0.338),
    (0.467, 0.366),
    (0.442, 0.402),
    (0.418, 0.403),
    (0.393, 0.390),
    (0.368, 0.342),
    (0.344, 0.344),
    (0.319, 0.409),
    (0.294, 0.403),
    (0.269, 0.402),
    (0.245, 0.406),
    (0.220, 0.363),
    (0.195, 0.365),
    (0.171, 0.372),
    (0.121, 0.375),
    (0.072, 0.372),
    (0.022, 0.359),
    (-0.027, 0.350),
    (-0.076, 0.325),
    (-0.126, 0.310),
    (-0.175, 0.328),
    (-0.225, 0.310),
    (-0.274, 0.307),
    (-0.323, 0.304),
    (-0.373, 0.325),
    (-0.422, 0.353),
    (-0.472, 0.418),
    (-0.521, 0.488),
    (-0.570, 0.630),
    (-0.620, 0.758),
    (-0.669, 0.849),
    (-0.719, 0.912),
    (-0.768, 0.967),
    (-0.818, 0.980),
    (-0.867, 1.012),
    (-0.892, 1.042),
    (-0.916, 1.042),
    (-0.941, 1.052),
    (-0.966, 1.058),
    (-0.990, 1.064),
    (-1.015, 1.069),
    (-1.065, 1.068),
    (-1.114, 1.068),
]

# Contour lines: the reference carries about thirty-five over the head, which
# used to be one line every eight footage rows. In world units that step is
# 0.0247, and keeping it means a retune never has to count rows again.
Y_TOP = 0.79
RUNOFF_Y = -1.46
LINE_DY = 0.0247

# Head width, as a fraction of the measured profile. The footage the profile
# was fitted to reads wide and blocky next to the current target: measured on
# captures, my head runs 1.15 wide-per-tall against the target's 0.86 (Claude
# still) and 0.70 (monitor footage), clouds included on both sides. 0.80 lands
# the render at ~0.92, the conservative end of that gap; push it down if the
# head still reads blocky. Applies across the face band only, blended back to
# 1.0 at the neck and the crown so neither junction steps.
HEAD_W = 0.80
HEAD_Y0 = 0.00
HEAD_Y1 = 0.10
HEAD_Y2 = 0.60
HEAD_Y3 = 0.72

# One point every this many world units along a line. It has to stay well
# under the particle's on-screen width or the stroke breaks into dashes:
# 0.0040 world units was over 1px at this framing and even 0.0024 still read
# as separate ticks.
POINT_STEP = 0.0016

# The warm face glow: centre x/y, half-width, half-height. A glow, so the
# ellipse is wider than the skull -- it fades, it does not clip. The width is
# tied to HEAD_W: the ellipse was fitted to the unslimmed head, and leaving it
# wide would spill the glow past the cheeks once the head narrows.
FACE_C = (0.0, 0.032)
FACE_RX = 0.448 * HEAD_W
FACE_RY = 0.510

# The gold veins: one quadratic bezier per side, from the neck down to the
# chest node, bowing outward through the trapezius. Points within VEIN_W of
# either curve read gold; points within NODE_R of the node do too, so the
# wishbone lands on the burst the renderer draws there.
VEIN_L = ((-0.085, -0.28), (-0.155, -0.68), (-0.008, -1.055))
VEIN_R = ((0.085, -0.28), (0.155, -0.68), (0.008, -1.055))
VEIN_W = 0.022
NODE = (0.0, -1.08)
NODE_R = 0.05

# Depth of the cross-section as a fraction of its width. A head is nearly as
# deep as it is wide; shoulders are wide and shallow. Perspective is what makes
# a horizontal ring bow when it is projected, so this number sets how much the
# contours wrap -- too flat and the lines come out as plain rules.
DEPTH_Y = [0.90, 0.40, 0.00, -0.30, -0.50, -0.70, -1.15]
DEPTH_R = [1.00, 1.00, 0.98, 0.90, 0.75, 0.50, 0.34]

# Particle radii. They have to be wide enough that consecutive samples along a
# line overlap -- additive blending only builds a stroke out of sprites that
# actually touch -- but the three body colours stay within 10% of one another
# so no band reads as coarser than its neighbour. The rim is deliberately
# fatter: it carries the outline on its own.
CYAN_SIZE = 0.0075
FACE_SIZE = 0.0079
GOLD_SIZE = 0.0072
RIM_SIZE = 0.0110

# The loose particles that hang off the silhouette. Three per row, thrown
# outward between CLOUD_NEAR and CLOUD_NEAR + CLOUD_SPREAD world units -- the
# far end is about 24px at the fitted framing, which is how far the reference's
# dots drift before they fade out. An isolated sprite stacks with nothing, so
# unlike the contour colours this one carries its own brightness.
CLOUD = (0.10, 0.60, 0.92)
CLOUD_SIZE = 0.0070
CLOUD_PER_ROW = 3
CLOUD_NEAR = 0.004
CLOUD_SPREAD = 0.078

# Contour colours, set for what they look like *added together* (see module
# docstring). Face gold brightens toward the middle of the glow.
CYAN = (0.07, 0.31, 0.48)
GOLD = (0.42, 0.23, 0.05)
RIM = (0.24, 0.60, 0.88)

# Only the front half of each ring is kept. Drawing both halves made every
# contour appear twice, interleaved, because perspective separates the near and
# far side of a ring by tens of pixels -- the bust came out twice as dense as
# intended, and the dim far half greyed out the near one. The far side is not
# missed: a ring still reaches its widest at u = +/-90 deg, which is exactly
# where the projected silhouette falls, so the outline is complete without it.


_PY, _PW = zip(*sorted(PROFILE))
_PY = np.array(_PY)
_PW = np.array(_PW)


def _tangents() -> np.ndarray:
    """Central-difference tangents, one per control point (ends one-sided)."""
    m = np.empty_like(_PW)
    m[0] = (_PW[1] - _PW[0]) / (_PY[1] - _PY[0])
    m[-1] = (_PW[-1] - _PW[-2]) / (_PY[-1] - _PY[-2])
    d = (_PW[2:] - _PW[:-2]) / (_PY[2:] - _PY[:-2])
    m[1:-1] = d
    return m


_M = _tangents()


def silhouette_rx(y: float) -> float:
    """Half-width of the bust at height y: cubic Hermite through PROFILE.

    C1 smooth by construction, so the contours never show the steps that row
    quantisation left in the measured version. Clamped at zero: above the
    crown tip the curve would go negative, and a negative width is a ring
    inside-out.
    """
    if y >= _PY[-1]:
        return 0.0
    if y <= _PY[0]:
        return float(_PW[0]) * _head_factor(y)
    i = int(np.searchsorted(_PY, y, side="right")) - 1
    h = _PY[i + 1] - _PY[i]
    t = (y - _PY[i]) / h
    t2, t3 = t * t, t * t * t
    w = ((2 * t3 - 3 * t2 + 1) * _PW[i]
         + (t3 - 2 * t2 + t) * h * _M[i]
         + (-2 * t3 + 3 * t2) * _PW[i + 1]
         + (t3 - t2) * h * _M[i + 1])
    return max(0.0, float(w)) * _head_factor(y)


def _head_factor(y: float) -> float:
    """1 outside the face band, HEAD_W inside, smoothstep ramps between."""
    def smooth(a: float, b: float, x: float) -> float:
        t = min(1.0, max(0.0, (x - a) / (b - a)))
        return t * t * (3 - 2 * t)
    return 1.0 - (1.0 - HEAD_W) * smooth(HEAD_Y0, HEAD_Y1, y) * (
        1.0 - smooth(HEAD_Y2, HEAD_Y3, y))


def _bezier(p0: tuple[float, float], p1: tuple[float, float],
            p2: tuple[float, float], n: int = 64) -> np.ndarray:
    t = np.linspace(0.0, 1.0, n)[:, None]
    a = np.array(p0) + t * (np.array(p1) - np.array(p0))
    b = np.array(p1) + t * (np.array(p2) - np.array(p1))
    return a + t * (b - a)


# Vein centrelines as (y, x) polylines running top to bottom, so the x of each
# vein at a ring's height is one interpolation away.
def _vein_yx(curve: tuple[tuple[float, float], tuple[float, float], tuple[float, float]],
             ) -> tuple[np.ndarray, np.ndarray]:
    pts = _bezier(*curve)
    order = np.argsort(pts[:, 1])
    return pts[order, 1], pts[order, 0]


_VEIN_LY, _VEIN_LX = _vein_yx(VEIN_L)
_VEIN_RY, _VEIN_RX = _vein_yx(VEIN_R)


def _hash01(row: int, salt: int) -> float:
    """Deterministic 0..1 from a row index and a salt.

    Used for the silhouette cloud. Random here would re-roll every particle on
    every bake, so the .bin would churn in git even when the parameters were
    untouched. This gives the same scatter every run while still being flat
    enough to look random.
    """
    h = (row * 2654435761 + salt * 40503) & 0xFFFFFFFF
    h ^= h >> 16
    return (h % 100000) / 100000.0


def depth_ratio(y: float) -> float:
    """Cross-section depth as a fraction of its width at height y."""
    return float(np.interp(y, DEPTH_Y, DEPTH_R))


def surface_normal(u: float, rx: float, rz: float, drx: float, drz: float) -> np.ndarray:
    """Outward normal of the cross-section at angle u, ignoring dy (it is 1)."""
    su, cu = np.sin(u), np.cos(u)
    # dP/du x dP/dy for P = (rx*sin u, y, rz*cos u)
    return np.array([
        rz * su,
        -(rz * drx * su * su + rx * drz * cu * cu),
        rx * cu,
    ])


def paint(px: float, y: float) -> tuple[tuple[float, float, float], float, float]:
    """Colour, glow and vein-ness of a world point, from the parameters.

    Returns (rgb, glow, vein). The veins are checked first: where they cross
    the face ellipse the gold wins, which is what the reference shows -- the
    wishbone stays readable over the glow instead of dissolving into it.
    """
    vein = min(
        abs(px - float(np.interp(y, _VEIN_LY, _VEIN_LX, left=9e9, right=9e9))),
        abs(px - float(np.interp(y, _VEIN_RY, _VEIN_RX, left=9e9, right=9e9))),
    )
    node = abs(complex(px - NODE[0], y - NODE[1]))
    if vein < VEIN_W or node < NODE_R:
        return GOLD, 0.0, 1.0
    fx, fy = FACE_C
    glow = max(0.0, 1.0 - ((px - fx) / FACE_RX) ** 2 - ((y - fy) / FACE_RY) ** 2)
    if glow > 0:
        return (0.44, 0.13 + 0.21 * glow, 0.010 + 0.036 * glow), glow, 0.0
    return CYAN, 0.0, 0.0


def main() -> None:
    n_lines = int((Y_TOP - RUNOFF_Y) / LINE_DY)
    ys = Y_TOP - np.arange(n_lines) * LINE_DY
    records: list[tuple[float, ...]] = []

    for li, y in enumerate(ys):
        rx = silhouette_rx(float(y))
        if rx < 0.02:
            continue
        rz = rx * depth_ratio(float(y))

        # Slope of the profile, needed for the normal. Finite difference on
        # the curve itself now -- no measurement noise left to smooth away.
        e = 0.004
        drx = (silhouette_rx(float(y) + e) - silhouette_rx(float(y) - e)) / (2 * e)
        drz = drx * depth_ratio(float(y)) + rx * (
            (depth_ratio(float(y) + e) - depth_ratio(float(y) - e)) / (2 * e))

        # How far around the ring one sample takes, so the count tracks the
        # circumference and the spacing stays even between a small head ring
        # and a wide shoulder ring.
        circumference = np.pi * (3 * (rx + rz) - np.sqrt((3 * rx + rz) * (rx + 3 * rz)))
        count = max(24, int(np.ceil(circumference / POINT_STEP)))

        for k in range(count):
            u = 2 * np.pi * k / count
            px, pz = rx * np.sin(u), rz * np.cos(u)
            if pz < 0:
                continue

            # Grazing angle: the surface turns away from the camera exactly
            # where the projected silhouette falls, and at the crown, where the
            # slope is steep. That is the whole of the reference's bright edge.
            n = surface_normal(u, rx, rz, drx, drz)
            grazing = 1.0 - abs(n[2]) / max(np.linalg.norm(n), 1e-9)

            (r, g, b), glow, vein = paint(px, float(y))

            if grazing > 0.72:
                # Ease into the rim colour rather than switching to it, so the
                # edge brightens without every contour changing hue. The
                # threshold is deliberately high: at 0.45 a quarter of the
                # whole bust was being pulled toward the pale edge colour,
                # which is what greyed the figure out.
                t = min(1.0, (grazing - 0.72) / 0.25)
                r = r + (RIM[0] - r) * t
                g = g + (RIM[1] - g) * t
                b = b + (RIM[2] - b) * t
                size = CYAN_SIZE + (RIM_SIZE - CYAN_SIZE) * t
            else:
                size = (FACE_SIZE if glow > 0
                        else GOLD_SIZE if vein > 0
                        else CYAN_SIZE)

            records.append((px, float(y), pz, r, g, b, size))

    # The silhouette, traced on its own. Each ring only lends the two points
    # where it turns edge-on, so stacking rings left the outline as a column of
    # separate dots while the reference's edge is one continuous bright band.
    # The projected outline of a stack of cross-sections is simply x = +-rx(y),
    # and it closes on itself at the crown where rx vanishes -- so follow that
    # curve one small step at a time. Nothing else in the bust carries it.
    rim_dy = LINE_DY / 8
    y = Y_TOP
    while y > RUNOFF_Y:
        rx = silhouette_rx(y)
        if rx >= 0.02:
            records.append((-rx, y, 0.0, *RIM, RIM_SIZE))
            records.append((rx, y, 0.0, *RIM, RIM_SIZE))
        y -= rim_dy

    # ...and hanging off it, the cloud. Magnify the reference's edge and the
    # outline is not a drawn line at all: a bright rim with loose particles
    # drifting outward, thinning as they go. The throw is deterministic per row
    # index (see _hash01) so the output is byte-identical run to run.
    row = 0
    y = Y_TOP
    while y > RUNOFF_Y:
        rx = silhouette_rx(y)
        if rx >= 0.02:
            for side in (-1.0, 1.0):
                for k in range(CLOUD_PER_ROW):
                    u = _hash01(row, k)
                    d = CLOUD_NEAR + CLOUD_SPREAD * (u ** 1.7)
                    dy = (_hash01(row, k + 11) - 0.5) * 0.030
                    dz = (_hash01(row, k + 23) - 0.5) * 0.070
                    records.append((side * (rx + d), y + dy, dz, *CLOUD, CLOUD_SIZE))
        row += 1
        y -= LINE_DY / 2

    points = np.asarray(records, dtype="<f4")
    OUT.write_bytes(struct.pack("<I", len(points)) + points.tobytes())
    print(f"Wrote {len(points)} particles to {OUT}")
    print(f"  world x {points[:, 0].min():.3f}..{points[:, 0].max():.3f}, "
          f"y {points[:, 1].min():.3f}..{points[:, 1].max():.3f}")


if __name__ == "__main__":
    main()
