"""Bake the hologram's head into a small particle file.

Source: TalkingHead's ``mpfb.glb`` avatar, made with Blender + MPFB and
licensed CC0 (public domain). We sample particles on the skin surface from
the chest up, keep them in thin horizontal bands so they read as contour
lines, and store how each particle moves for the jawOpen / viseme_aa /
eyeBlink blend shapes, so the hologram can talk and blink.

Usage:  python drishti/bake_hologram_head.py path/to/mpfb.glb
Writes: drishti/hologram-head.bin

Format (little endian): uint32 count, then per point 13 x int16:
position xyz, jaw delta xyz, "aa" delta xyz, blink delta xyz, region
(0 skin, 1 eye, 2 lips). Coordinates are metres * SCALE, centred on the head.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import numpy as np
from pygltflib import GLTF2

SCALE = 8000
OUT = Path(__file__).resolve().parent / "hologram-head.bin"
_TYPES = {5126: np.float32, 5123: np.uint16, 5125: np.uint32, 5121: np.uint8}
_SIZES = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def _view(g, blob, view_index, offset, dtype, count, n):
    view = g.bufferViews[view_index]
    start = (view.byteOffset or 0) + (offset or 0)
    return np.frombuffer(blob, dtype=dtype, count=count * n, offset=start).reshape(count, n) if n > 1 else \
        np.frombuffer(blob, dtype=dtype, count=count, offset=start)


def read(g: GLTF2, blob: bytes, index: int) -> np.ndarray:
    acc = g.accessors[index]
    if acc.bufferView is None:  # sparse accessor (blend shape deltas): zeros plus listed values
        n = _SIZES[acc.type]
        out = np.zeros((acc.count, n), dtype=np.float32)
        sp = acc.sparse
        if sp is not None:
            idx = _view(g, blob, sp.indices.bufferView, sp.indices.byteOffset, _TYPES[sp.indices.componentType], sp.count, 1)
            out[idx] = _view(g, blob, sp.values.bufferView, sp.values.byteOffset, np.float32, sp.count, n)
        return out
    view = g.bufferViews[acc.bufferView]
    dtype = _TYPES[acc.componentType]
    n = _SIZES[acc.type]
    start = (view.byteOffset or 0) + (acc.byteOffset or 0)
    stride = view.byteStride or np.dtype(dtype).itemsize * n
    raw = np.frombuffer(blob, dtype=np.uint8, count=stride * (acc.count - 1) + np.dtype(dtype).itemsize * n,
                        offset=start)
    out = np.lib.stride_tricks.as_strided(raw, shape=(acc.count, np.dtype(dtype).itemsize * n), strides=(stride, 1))
    return np.ascontiguousarray(out).view(dtype).reshape(acc.count, n).squeeze()


def mesh_data(g, blob, name, targets=("jawOpen", "viseme_aa", "eyeBlinkLeft", "eyeBlinkRight")):
    mesh = next(m for m in g.meshes if m.name == name)
    prim = mesh.primitives[0]
    pos = read(g, blob, prim.attributes.POSITION).astype(np.float64)
    tri = read(g, blob, prim.indices).reshape(-1, 3)
    names = (mesh.extras or {}).get("targetNames", [])
    deltas = {}
    for t in targets:
        if t in names:
            deltas[t] = read(g, blob, prim.targets[names.index(t)]["POSITION"]).astype(np.float64)
        else:
            deltas[t] = np.zeros_like(pos)
    return pos, tri, deltas


def sample(pos, tri, deltas, count, rng, keep=lambda p: np.ones(len(p), bool)):
    a, b, c = pos[tri[:, 0]], pos[tri[:, 1]], pos[tri[:, 2]]
    area = np.linalg.norm(np.cross(b - a, c - a), axis=1) / 2
    centre = (a + b + c) / 3
    area = area * keep(centre)
    pick = rng.choice(len(tri), size=count * 3, p=area / area.sum())
    u, v = rng.random(len(pick)), rng.random(len(pick))
    flip = u + v > 1
    u[flip], v[flip] = 1 - u[flip], 1 - v[flip]
    w = 1 - u - v
    t = tri[pick]

    def interp(arr):
        return arr[t[:, 0]] * w[:, None] + arr[t[:, 1]] * u[:, None] + arr[t[:, 2]] * v[:, None]

    p = interp(pos)
    d = {k: interp(val) for k, val in deltas.items()}
    return p, d


def main(src: str) -> None:
    g = GLTF2().load(src)
    blob = g.binary_blob()
    rng = np.random.default_rng(7)
    pos, tri, deltas = mesh_data(g, blob, "base")
    head_y = pos[:, 1].max() - 0.12  # roughly the eyes
    cut = head_y - 0.62  # mid chest

    p, d = sample(pos, tri, deltas, 38000, rng, keep=lambda c: c[:, 1] > cut)
    # Contour lines: keep thin horizontal bands, plus a sparse fill.
    band = ((p[:, 1] - cut) / 0.0085) % 1.0
    keep = (band < 0.22) | (rng.random(len(p)) < 0.06)
    p, d = p[keep], {k: v[keep] for k, v in d.items()}

    jaw, aa = d["jawOpen"], d["viseme_aa"]
    blink = d["eyeBlinkLeft"] + d["eyeBlinkRight"]
    moving = np.linalg.norm(jaw + aa, axis=1)
    region = np.where(moving > 0.004, 2, 0)

    # Eyes: the "high-poly" mesh, a few hundred bright points.
    epos, etri, edel = mesh_data(g, blob, "high-poly")
    ep, ed = sample(epos, etri, edel, 700, rng)
    p = np.vstack([p, ep])
    jaw = np.vstack([jaw, ed["jawOpen"]])
    aa = np.vstack([aa, ed["viseme_aa"]])
    blink = np.vstack([blink, ed["eyeBlinkLeft"] + ed["eyeBlinkRight"]])
    region = np.concatenate([region, np.ones(len(ep), int)])

    centre = np.array([0.0, head_y, np.median(p[:, 2])])
    p = p - centre
    cols = [p, jaw, aa, blink]
    arr = np.hstack([np.round(c * SCALE) for c in cols] + [region[:, None]]).astype(np.int16)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(struct.pack("<I", len(arr)) + arr.tobytes())
    print(f"{len(arr)} points -> {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "mpfb.glb")
