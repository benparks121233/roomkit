#!/usr/bin/env python3
"""
Strip shadow halos from transparent PNGs using flood-fill from edges.

The shadow is painted as opaque warm cream pixels connected to the transparent
border. We flood-fill from transparent edges into adjacent "shadow-like" pixels:
light, warm-toned, NOT green/blue (to preserve leaf highlights etc).

Usage: python3 scripts/clean-alpha.py [--threshold LUMA] <file1.png> [file2.png ...]
"""

import sys
from PIL import Image
import numpy as np
from collections import deque


def get_hue_sat(r, g, b):
    """Return (hue 0-360, saturation 0-255) arrays."""
    r_f, g_f, b_f = r.astype(float), g.astype(float), b.astype(float)
    mx = np.maximum(np.maximum(r_f, g_f), b_f)
    mn = np.minimum(np.minimum(r_f, g_f), b_f)
    delta = mx - mn

    sat = np.where(mx > 0, (delta / mx) * 255, 0).astype(int)

    hue = np.zeros_like(r_f)
    mask = delta > 0
    # Red is max
    rm = mask & (mx == r_f)
    hue[rm] = 60 * (((g_f[rm] - b_f[rm]) / delta[rm]) % 6)
    # Green is max
    gm = mask & (mx == g_f) & ~rm
    hue[gm] = 60 * (((b_f[gm] - r_f[gm]) / delta[gm]) + 2)
    # Blue is max
    bm = mask & (mx == b_f) & ~rm & ~gm
    hue[bm] = 60 * (((r_f[bm] - g_f[bm]) / delta[bm]) + 4)

    return hue.astype(int) % 360, sat


def is_shadow_pixel(r, g, b, a, luma_min=160):
    """
    Return boolean mask: True where pixel looks like shadow/halo.
    Shadow = warm-toned (not green/blue), light, relatively desaturated.
    """
    luma = 0.299 * r.astype(float) + 0.587 * g.astype(float) + 0.114 * b.astype(float)
    hue, sat = get_hue_sat(r, g, b)

    # Shadow characteristics:
    # - Light (high luminance)
    # - Warm hue: reds, oranges, yellows, warm neutrals (hue 0-60 or 300-360)
    #   NOT green (60-180), NOT blue (180-300)
    # - Relatively desaturated (sat < 100)
    is_warm = (hue <= 60) | (hue >= 300)
    is_light = luma >= luma_min
    is_desat = sat <= 100
    is_visible = a > 0

    return is_light & is_warm & is_desat & is_visible


def clean_image(filepath, luma_min=160):
    print(f"Processing {filepath} (luma_min={luma_min})...")
    img = Image.open(filepath).convert("RGBA")
    data = np.array(img)
    h, w = data.shape[:2]

    r, g, b, a = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]

    shadow_eligible = is_shadow_pixel(r, g, b, a, luma_min)
    seed_mask = a <= 10  # transparent pixels

    to_erase = np.zeros((h, w), dtype=bool)
    visited = np.zeros((h, w), dtype=bool)

    queue = deque()

    # Seed from ALL transparent pixels
    ys, xs = np.where(seed_mask)
    for y_val, x_val in zip(ys, xs):
        visited[y_val, x_val] = True
        queue.append((y_val, x_val))

    # BFS flood fill: transparent → adjacent shadow → adjacent shadow → ...
    while queue:
        cy, cx = queue.popleft()
        for dy, dx in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]:
            ny, nx = cy+dy, cx+dx
            if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx]:
                visited[ny, nx] = True
                if seed_mask[ny, nx]:
                    queue.append((ny, nx))
                elif shadow_eligible[ny, nx]:
                    to_erase[ny, nx] = True
                    queue.append((ny, nx))

    erased = np.sum(to_erase)
    total_visible = np.sum(a > 0)

    data[to_erase, 3] = 0

    result = Image.fromarray(data)
    result.save(filepath)

    print(f"  Erased {erased} shadow pixels ({erased/max(total_visible,1)*100:.1f}% of visible)")
    print(f"  Saved {filepath}")


# Parse args
args = sys.argv[1:]
luma = 160
files = []
i = 0
while i < len(args):
    if args[i] == "--threshold" and i + 1 < len(args):
        luma = int(args[i+1])
        i += 2
    else:
        files.append(args[i])
        i += 1

for f in files:
    clean_image(f, luma)
