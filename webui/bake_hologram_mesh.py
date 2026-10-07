"""Bake the hologram as horizontal isolines cut from a parametric bust.

Usage: python webui/bake_hologram_mesh.py path/to/reference.mp4 [time-seconds]
Requires OpenCV and NumPy. Writes webui/hologram-points.bin.

Why this exists instead of `bake_hologram_reference.py`:

That script lifts edge pixels straight out of the footage, so its lines are as
good as a phone photograph of a monitor allows -- 2px runs behind a 6px median
gap, with camera moiré on top. No amount of filtering separates the noise from
a stroke that is itself only two pixels tall.

The reference clip is not a photograph of points; it is a solid bust sliced
into horizontal contour lines. So this script rebuilds that geometry: it takes
the *silhouette* from the footage (the one thing a photo measures reliably),
extrudes it into a closed cross-section, and cuts that cross-section at regular
heights. The wrap around the skull, the nested arcs over the shoulders and the
clean bright rim are then consequences of the geometry rather than of pixels,
and they survive at any zoom.

Colours still come from the footage, so the gold veins across the chest and the
warm face glow stay exactly where the reference puts them.

The output is the same 7-float record the renderer already reads -- x, y, z,
r, g, b, size -- so the renderer needs no changes at all.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import cv2
import numpy as np

OUT = Path(__file__).resolve().parent / "hologram-points.bin"

# Footage -> world. x and y share one factor: x spans 625px about the centre
# below the mirror line exactly as y does, and giving them separate scales is
# what stretched the bust 1.82x wide in the first place.
CX = 350.0
Y_TOP_SRC = 205.0
SCALE = 1.93 / 625

# One contour line every this many footage rows, and one point every this many
# world units along a line. The row step sets how many lines the bust carries --
# the reference shows about thirty-five over the head, which is a line every
# eight footage rows. The along-line step has to stay well under the particle's
# on-screen width or the stroke breaks into dashes: 0.0040 world units was over
# 1px at this framing and even 0.0024 still read as separate ticks.
CUT_ROWS = 8
POINT_STEP = 0.0016

# How small a blob may be before it is taken for spray, and how few pixels a
# row may hold before its edge is taken for the silhouette. Both are small on
# purpose. Around the crown the contour lines are themselves short segments of
# only a few pixels, and a minimum component area of 25 -- the first guess --
# deleted the entire top of the head; np.interp then back-filled the gap with
# whatever the last surviving row below it measured, which is why the skull
# came out as a cone. Sprayed droplets are individual pixels and die at 6.
MIN_COMPONENT = 6
MIN_ROW_PIXELS = 6

# How far past the monitor the chest is extended. The footage stops at the
# bottom of the screen, so what is below it cannot be measured -- but the
# reference clearly has the shoulders running out of frame, and the renderer
# already fades the body out across y = -1.45..-1.2, which is exactly where a
# run-off to -1.46 lands. Holding the last measured width there costs nothing
# and removes the visible hem the bust used to end on.
RUNOFF_Y = -1.46

# The warm face glow in footage pixels: centre x, centre y, half-width, height.
FACE = (350.0, 470.0, 145.0, 165.0)

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

# Colours are set for what they look like *added together*, not on their own.
# A line is built from sprites spaced 0.0016 world units apart and 0.0075 wide,
# so roughly four of them land on every pixel of the stroke; taking these
# numbers at face value stacks green and blue past 1.0, they clip, and the
# stroke comes out grey-white where the reference is cyan. Measured on the
# capture: the reference's lit pixels run 76/125/128 at saturation 111, an
# early version of this bake ran 107/121/118 at saturation 59.
CYAN = (0.07, 0.31, 0.48)
GOLD = (0.42, 0.23, 0.05)
RIM = (0.24, 0.60, 0.88)

# Only the front half of each ring is kept. Drawing both halves made every
# contour appear twice, interleaved, because perspective separates the near and
# far side of a ring by tens of pixels -- the bust came out twice as dense as
# intended, and the dim far half greyed out the near one. The far side is not
# missed: a ring still reaches its widest at u = +/-90 deg, which is exactly
# where the projected silhouette falls, so the outline is complete without it.


def frame_masks(path: str, seconds: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (colour frame, warm mask, cyan mask) at the given time."""
    video = cv2.VideoCapture(path)
    video.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
    ok, frame = video.read()
    video.release()
    if not ok:
        raise SystemExit(f"Could not read frame at {seconds:.2f}s from {path}")

    hue, sat, val = cv2.split(cv2.cvtColor(frame, cv2.COLOR_BGR2HSV))
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    detail = cv2.subtract(gray, cv2.GaussianBlur(gray, (0, 0), sigmaX=5, sigmaY=5))
    roi = (np.indices(gray.shape)[1] < 530)
    cyan = roi & (hue >= 72) & (hue <= 112) & (sat >= 55) & (val >= 55) & (detail > 8)
    warm = roi & (hue >= 5) & (hue <= 38) & (sat >= 55) & (val >= 55) & (detail > 8)
    return frame, warm, cyan


def measure_width(warm: np.ndarray, cyan: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Per-row half-width about CX in world units, NaN where unmeasured.

    Only the left half is trusted: the ROI clips the right shoulder at x=530,
    so the left edge is the only one that still measures the real figure.
    Dropping small components first matters -- the reference sprays loose
    droplets around the crown, and a single stray pixel on the left of a row
    would read as a shoulder twice its real width.
    """
    mask = (warm | cyan).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    if n > 1:
        keep = np.zeros(n, bool)
        keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= MIN_COMPONENT
        mask = keep[labels].astype(np.uint8)

    rows = np.arange(190, 851)
    width = np.full(rows.shape, np.nan)
    for i, y in enumerate(rows):
        xs = np.flatnonzero(mask[y])
        if xs.size < MIN_ROW_PIXELS:
            continue
        # Ignore a lone outlier by taking the edge of the densest run
        # rather than the bare minimum.
        left = np.percentile(xs, 1)
        width[i] = (CX - left) * SCALE
    return rows, width


def silhouette_width(warm: np.ndarray, cyan: np.ndarray) -> np.ndarray:
    """`measure_width` with the gaps filled, the tail held and the jitter gone."""
    rows, width = measure_width(warm, cyan)
    if np.isfinite(width).sum() < 10:
        raise SystemExit("No silhouette found in frame -- wrong timestamp?")

    # The bust only ever widens as it runs down through the shoulders, so a
    # row that falls far below the widest value already seen is the monitor
    # edge eating the figure, not the body narrowing. Blank those rows before
    # interpolating: np.interp then holds the last real width instead of
    # dragging the chest down to the glare it measured below the screen.
    # The neck IS narrower than the shoulders, which is why this only applies
    # past the widest row rather than to every row.
    peak = int(np.nanargmax(width))
    tail = width.copy()
    tail[peak + 1:][width[peak + 1:] < 0.80 * width[peak]] = np.nan
    valid = np.isfinite(tail)
    width = np.interp(rows, rows[valid], tail[valid])

    # A running median smooths the jitter of a photographed edge. 15 rows is
    # wide enough to kill that and narrow enough not to round off the crown.
    pad = np.pad(width, 7, mode="edge")
    width = np.median(np.lib.stride_tricks.sliding_window_view(pad, 15), axis=1)
    return np.clip(width, 0.0, 350 * SCALE)


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


def sample_colour(warm: np.ndarray, cyan: np.ndarray, sx: float, sy: float,
                  glow: float) -> tuple[float, float, float]:
    """Colour of the footage at a world point, mapped back through the bake."""
    h, w = warm.shape
    x, y = int(round(sx)), int(round(sy))
    if 0 <= x < w and 0 <= y < h:
        x0, x1 = max(0, x - 3), min(w, x + 4)
        y0, y1 = max(0, y - 3), min(h, y + 4)
        if warm[y0:y1, x0:x1].any():
            # Same accumulated-brightness reasoning as CYAN above: these are
            # the values a line of overlapping face sprites should stack to.
            return ((0.44, 0.13 + 0.21 * glow, 0.010 + 0.036 * glow)
                    if glow > 0 else GOLD)
        if cyan[y0:y1, x0:x1].any():
            return CYAN
    return CYAN


def main(path: str, seconds: float = 4.8) -> None:
    frame, warm, cyan = frame_masks(path, seconds)
    rows, raw = measure_width(warm, cyan)
    width = silhouette_width(warm, cyan)

    # Cut only where the footage actually measures the bust. Rows above the
    # crown hold nothing but spray and come back NaN; cutting there hangs a
    # ring in empty air over the head, which is what turned the skull into a
    # cone the first time round.
    measured = np.flatnonzero(np.isfinite(raw))
    lo, hi = int(measured[0]), int(measured[-1])

    # Run the profile past the bottom of the screen. What lies below it cannot
    # be measured, so the last real width is simply held: the chest then leaves
    # frame the way the reference's shoulders do, instead of ending on a
    # visible hem. The renderer already fades the body out across y = -1.45..-1.2.
    # NOTE: `rows` holds source rows while `lo`/`hi` are indices into it, so the
    # tail has to continue from rows[hi] -- arange(hi+1, ...) silently restarted
    # at 652 and re-cut rows 652..841 a second time, giving each of them a
    # correct ring and a second ring wearing the held chest width.
    runoff = int(np.ceil(Y_TOP_SRC + (0.85 - RUNOFF_Y) / SCALE))
    tail_rows = np.arange(rows[hi] + 1, runoff + 1)
    cut_rows = np.concatenate([rows[lo:hi + 1], tail_rows])
    cut_w = np.concatenate([width[lo:hi + 1], np.full(len(tail_rows), width[hi])])

    fx, fy, frx, fry = FACE
    records: list[tuple[float, ...]] = []

    for idx in range(0, len(cut_rows), CUT_ROWS):
        src_y = cut_rows[idx]
        y = 0.85 - (src_y - Y_TOP_SRC) * SCALE
        rx = float(cut_w[idx])
        if rx < 0.02:
            continue
        rz = rx * depth_ratio(y)

        # Slope of the profile, needed for the normal. One step either side is
        # enough -- the silhouette is smooth once it has been median-filtered.
        dy = SCALE
        drx = ((cut_w[min(idx + 1, len(cut_w) - 1)] - cut_w[max(idx - 1, 0)])
               / (2 * dy)) if 0 < idx < len(cut_w) - 1 else 0.0
        drz = drx * depth_ratio(y) + rx * (
            (depth_ratio(y + dy) - depth_ratio(y - dy)) / (2 * dy))

        # How far around the ring one sample takes, so the count tracks the
        # circumference and the spacing stays even between a small head ring
        # and a wide shoulder ring.
        circumference = np.pi * (3 * (rx + rz) - np.sqrt((3 * rx + rz) * (rx + 3 * rz)))
        count = max(24, int(np.ceil(circumference / POINT_STEP)))

        for k in range(count):
            u = 2 * np.pi * k / count
            px, pz = rx * np.sin(u), rz * np.cos(u)
            if pz < 0:
                # The far half of the ring is dropped, not dimmed -- see the
                # note about interleaved contours near the top of this file.
                continue

            # Grazing angle: the surface turns away from the camera exactly
            # where the projected silhouette falls, and at the crown, where the
            # slope is steep. That is the whole of the reference's bright edge.
            n = surface_normal(u, rx, rz, drx, drz)
            grazing = 1.0 - abs(n[2]) / max(np.linalg.norm(n), 1e-9)

            sx = CX + px / SCALE
            sy = Y_TOP_SRC + (0.85 - y) / SCALE
            glow = max(0.0, 1.0 - ((sx - fx) / frx) ** 2 - ((sy - fy) / fry) ** 2)
            r, g, b = sample_colour(warm, cyan, sx, sy, glow)

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
                        else GOLD_SIZE if (b < 0.5 and r > 0.7)
                        else CYAN_SIZE)

            records.append((px, y, pz, r, g, b, size))

    # The silhouette, traced on its own. Each ring only lends the two points
    # where it turns edge-on, so stacking rings left the outline as a column of
    # separate dots while the reference's edge is one continuous bright band.
    # The projected outline of a stack of cross-sections is simply x = +-rx(y),
    # and it closes on itself at the crown where rx vanishes -- so follow that
    # curve one footage row at a time, which lands at 0.003 world units apart,
    # about a third of a pixel. Nothing else in the bust carries the outline.
    for j in range(len(cut_rows)):
        y = 0.85 - (cut_rows[j] - Y_TOP_SRC) * SCALE
        rx = float(cut_w[j])
        if rx < 0.02:
            continue
        records.append((-rx, y, 0.0, *RIM, RIM_SIZE))
        records.append((rx, y, 0.0, *RIM, RIM_SIZE))

    points = np.asarray(records, dtype="<f4")
    OUT.write_bytes(struct.pack("<I", len(points)) + points.tobytes())
    print(f"Wrote {len(points)} particles to {OUT}")
    print(f"  {len(range(0, len(cut_rows), CUT_ROWS))} contour lines, "
          f"world x {points[:, 0].min():.3f}..{points[:, 0].max():.3f}, "
          f"y {points[:, 1].min():.3f}..{points[:, 1].max():.3f}")


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 4.8)
