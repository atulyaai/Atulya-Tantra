"""Bake hologram scanline points from the user's reference video.

Usage: python webui/bake_hologram_reference.py path/to/reference.mp4 [time-seconds]
Requires OpenCV and NumPy. Writes webui/hologram-points.bin.
"""
from __future__ import annotations
import struct
import sys
from pathlib import Path
import cv2
import numpy as np

OUT = Path(__file__).resolve().parent / "hologram-points.bin"


def fill_gaps(m: np.ndarray, gap: int) -> np.ndarray:
    """Bridge short column gaps inside a single scanline.

    The high-pass keeps only each stroke's edge pixels, so one drawn rule comes
    back as two runs of dots with empty columns between them. Filling gaps up
    to `gap` px reconnects those runs into a continuous line. The gap limit
    matters: without it the fill would walk straight across the wider spaces
    that separate one contour line from the next and weld them together.
    """
    out = np.zeros_like(m)
    for y in range(m.shape[0]):
        xs = np.flatnonzero(m[y])
        if xs.size == 0:
            continue
        out[y, xs] = True
        for a, b in zip(xs[:-1], xs[1:]):
            if 1 < b - a <= gap:
                out[y, a + 1:b] = True
    return out


def despeckle(m: np.ndarray, min_area: int = 6) -> np.ndarray:
    """Drop the photographic noise the high-pass was keeping.

    The reference frame is a phone photograph of a monitor, so `detail > 8`
    fires on sensor noise as readily as on a real contour stroke. Those specks
    sit a few pixels apart and would otherwise be welded into the figure by the
    gap fill, which is where the salt-and-pepper surface came from. A 3x3
    opening would be the textbook tool, but the strokes themselves are only
    2 px tall and eroding would erase them outright, so the filter is by
    connected area instead: a real stroke is thin *but long*, a speck is
    neither.
    """
    n, labels, stats, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), 8)
    if n <= 1:
        return m
    keep = np.zeros(n, bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= min_area
    return keep[labels]


def _smooth_closed(pts: np.ndarray, k: int) -> np.ndarray:
    """Circular moving average along a closed contour."""
    n = len(pts)
    if n < 4 * k + 1:
        return pts
    ext = np.vstack([pts[-k:], pts, pts[:k]])
    ker = np.full(2 * k + 1, 1.0 / (2 * k + 1))
    return np.stack([
        np.convolve(ext[:, 0], ker, mode="valid"),
        np.convolve(ext[:, 1], ker, mode="valid"),
    ], axis=1)


def silhouette(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return (solid figure, its outline).

    The reference draws a continuous bright edge around the whole bust; the
    point cloud had no equivalent layer, so the silhouette dissolved into
    loose particles instead of reading as a shape. Closing the scanline gaps
    welds the strokes into one region, filling the contours removes the gaps
    between them, and what survives an erosion of that region is the outline.
    """
    welded = cv2.morphologyEx(
        (mask.astype(np.uint8)) * 255, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8)
    )
    # RETR_CCOMP returns holes as the second hierarchy level; drawing every
    # contour filled paints over them, which is the hole fill.
    contours, _ = cv2.findContours(welded, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros_like(welded)
    cv2.drawContours(filled, contours, -1, 255, -1)
    # Outline the outer contour only. Eroding the filled region instead also
    # traced every hole that survived, which painted blocky internal edges
    # across the jaw and chest. Tiny stray blobs are filtered out so the loose
    # spray above the head is not given a ring of its own.
    external, _ = cv2.findContours(filled, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    outline = np.zeros_like(filled)
    for contour in external:
        if cv2.contourArea(contour) < 400:
            continue
        # CHAIN_APPROX_NONE returns every boundary pixel, so drawing it straight
        # gives a staircase at whatever scale the silhouette happens to kink.
        # Averaging along the closed contour first turns those steps into a
        # smooth curve -- the reference's rim is one clean edge, not jaggy.
        pts = _smooth_closed(contour.reshape(-1, 2).astype(np.float64), 7)
        cv2.polylines(outline, [np.round(pts).astype(np.int32)], True, 255, 1)
    return filled.astype(bool), outline.astype(bool)


def main(path: str, seconds: float = 4.8) -> None:
    video = cv2.VideoCapture(path)
    video.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
    ok, frame = video.read()
    video.release()
    if not ok:
        raise SystemExit(f"Could not read frame at {seconds:.2f}s from {path}")

    b, g, r = cv2.split(frame)
    yy, xx = np.indices(r.shape)
    roi = (xx < 530) & (yy >= 190) & (yy <= 850)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    hue, saturation, value = cv2.split(hsv)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    detail = cv2.subtract(gray, cv2.GaussianBlur(gray, (0, 0), sigmaX=5, sigmaY=5))
    # The dark monitor background has low saturation. Keeping only the colored
    # strokes avoids baking its photographed noise into the hologram.
    cyan = (roi & (hue >= 72) & (hue <= 112) & (saturation >= 55)
            & (value >= 55) & (detail > 8))
    warm = (roi & (hue >= 5) & (hue <= 38) & (saturation >= 55)
            & (value >= 55) & (detail > 8))

    # Denoise first: the gap fill walks up to 14 px looking for a neighbour,
    # so a speck left in place would simply be absorbed into the figure.
    raw_cyan, raw_warm = int(cyan.sum()), int(warm.sum())
    cyan = despeckle(cyan)
    warm = despeckle(warm)

    # Close each colour class on its own, so a warm stroke never gets bridged
    # with the cyan one beside it. 14 px is measured, not guessed: the source
    # hands back 2 px runs separated by a 6 px median gap (p75 = 12), so a 7 px
    # budget left 44% of every line dotted. Distinct contour lines are ~10 px
    # apart *vertically*, so a horizontal budget cannot merge them, and the
    # separations that matter structurally -- the gap across the neck, the
    # edge of the silhouette -- run far wider than 14.
    cyan = fill_gaps(cyan, 14)
    warm = fill_gaps(warm, 14)
    print(f"  denoise: cyan {raw_cyan} -> {int(cyan.sum())}, warm {raw_warm} -> {int(warm.sum())}")

    face = ((xx - 350) ** 2 / 145**2 + (yy - 470) ** 2 / 165**2) < 1
    face_lines = warm & face & (yy < 570)
    gold = warm & (yy >= 570)
    mask = cyan | warm
    _, outline = silhouette(mask)
    # The outline can sit a pixel or two outside the strokes after the close,
    # so merge it in to guarantee the rim is baked rather than missed.
    mask = mask | outline

    # Pixels of the reference to world units, applied to both axes alike.
    # y spans 205..830 (625 px) and maps to 1.93 units.
    scale = 1.93 / 625

    # Particle radii. The gap fill now supplies continuity, so the points only
    # have to supply thickness -- which makes them small. At the earlier sizes
    # a continuous line was 2.2 px wide and the rows nearly touched, so the
    # head fused into one solid mass; these hold the strokes apart and leave
    # the dark band between contour lines that the reference reads by. Kept
    # within ~25% of one another so no band is conspicuously coarser.
    CYAN_SIZE = 0.0055
    FACE_SIZE = 0.0058
    GOLD_SIZE = 0.0052
    # The rim is one pixel wide by construction, so it can afford to be a
    # little larger and considerably brighter than the contours it frames --
    # at parity with the cyan it disappeared into the figure instead of
    # drawing the edge.
    RIM_SIZE = 0.008
    RIM_COLOR = (0.7, 1.45, 2.1)

    records: list[tuple[float, ...]] = []
    ys, xs = np.where(mask)
    # x and y must share one scale. They did not: x used 0.82*2.4/350 per pixel
    # above y=570 and 1.25*2.4/350 below it, while y used 1.93/625. That is a
    # 1.52x jump across a single row and a 1.82x horizontal stretch overall, so
    # the head baked 1.55 wide-to-tall when the reference measures 0.851, and
    # the shoulders reached x=+-3.0 into a shader that hides everything past
    # 1.55 -- half the shoulder span simply never drew. One factor for both
    # axes keeps the reference's proportions and lands the shoulders inside the
    # fade.
    for x, y in zip(xs.tolist(), ys.tolist()):
        rim = bool(outline[y, x])
        warm_px = bool(gold[y, x] or face_lines[y, x])
        face_warm = bool(face_lines[y, x])
        # The camera crops the right shoulder at the ROI edge; mirror the intact
        # left half about the head centre (x=350) to restore a whole bust. The
        # head itself is not cropped, so only the body is mirrored. The rim
        # rides along with whichever half it belongs to.
        mirrored = y >= 570 and x < 350 and not warm_px
        if y >= 570 and x >= 350 and not warm_px:
            continue
        positions = (x, 700 - x) if mirrored else (x,)
        for px in positions:
            scene_x = (px - 350) * scale
            scene_y = 0.85 - (y - 205) * scale
            if rim:
                color, size = RIM_COLOR, RIM_SIZE
            elif warm_px:
                if face_warm:
                    glow = max(0.0, 1.0 - ((x - 350) / 120) ** 2 - ((y - 470) / 145) ** 2)
                    color = (1.1, 0.32 + 0.52 * glow, 0.025 + 0.09 * glow)
                    size = FACE_SIZE
                else:
                    color = (1.05, 0.58, 0.12)
                    size = GOLD_SIZE
            else:
                color = (0.18, 0.78, 1.2)
                size = CYAN_SIZE
            records.append((scene_x, scene_y, 0.12, *color, size))

    points = np.asarray(records, dtype="<f4")
    OUT.write_bytes(struct.pack("<I", len(points)) + points.tobytes())
    rim_n = sum(1 for rec in records if rec[6] == RIM_SIZE)
    print(f"Wrote {len(points)} particles to {OUT} ({rim_n} rim)")


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 4.8)
