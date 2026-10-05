"""Bake hologram scanline points from the user's reference video.

Usage: python drishti/bake_hologram_reference.py path/to/reference.mp4 [time-seconds]
Requires OpenCV and NumPy. Writes drishti/hologram-points.bin.
"""
from __future__ import annotations
import struct
import sys
from pathlib import Path
import cv2
import numpy as np

OUT = Path(__file__).resolve().parent / "hologram-points.bin"

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
    face = ((xx - 350) ** 2 / 145**2 + (yy - 470) ** 2 / 165**2) < 1
    face_lines = warm & face & (yy < 570)
    gold = warm & (yy >= 570)
    mask = cyan | warm

    records: list[tuple[float, ...]] = []
    ys, xs = np.where(mask)
    for x, y in zip(xs.tolist(), ys.tolist()):
        warm = bool(gold[y, x] or face_lines[y, x])
        face_warm = bool(face_lines[y, x])
        # The camera crops the left shoulder; mirror its measured scanlines to restore
        # the complete, symmetric bust while retaining the captured head contours.
        mirrored = y >= 570 and x < 350 and not warm
        if y >= 570 and x >= 350 and not warm:
            continue
        positions = (x, 700 - x) if mirrored else (x,)
        for px in positions:
            # The reference camera is unusually wide: in the actual figure the
            # head is much narrower than the shoulder span. Preserve that ratio
            # instead of letting a screen-width mapping turn the bust into an oval.
            scene_x = (px - 350) * ((0.82 if y < 570 else 1.25) * 2.4 / 350)
            scene_y = 0.85 - (y - 205) * (1.93 / 625)
            if warm:
                if face_warm:
                    glow = max(0.0, 1.0 - ((x - 350) / 120) ** 2 - ((y - 470) / 145) ** 2)
                    color = (1.1, 0.32 + 0.52 * glow, 0.025 + 0.09 * glow)
                    size = 0.0115
                else:
                    color = (1.05, 0.58, 0.12)
                    size = 0.0085
            else:
                color = (0.18, 0.78, 1.2)
                size = 0.0095
            records.append((scene_x, scene_y, 0.12, *color, size))

    points = np.asarray(records, dtype="<f4")
    OUT.write_bytes(struct.pack("<I", len(points)) + points.tobytes())
    print(f"Wrote {len(points)} particles to {OUT}")

if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 4.8)
