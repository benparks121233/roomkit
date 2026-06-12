#!/usr/bin/env python3
"""
Extract just the wood frame from bed.png.
bed.png stays as the full dressed bed (layer 2).
bed_frame.png is wood-only (layer 1).
"""

import numpy as np
from PIL import Image, ImageFilter
import os

SRC = "public/room-assets/bed.png"
OUT = "public/room-assets"

img = Image.open(SRC).convert("RGBA")
data = np.array(img)
h, w = data.shape[:2]

r, g, b, a = data[:,:,0].astype(float), data[:,:,1].astype(float), data[:,:,2].astype(float), data[:,:,3].astype(float)

# Wood detection: warm, dark-ish, red > blue, not too bright
luma = 0.299 * r + 0.587 * g + 0.114 * b

# Blue detection (to exclude)
is_blue = (b > r + 10) & (b > 110)

# Wood: warm brown tones. R > G > B, moderate luminance
wood = (
    (a > 10) &
    (r > b + 15) &           # warm (red > blue)
    (r > g) &                # red dominant
    (luma > 50) &            # not black
    (luma < 185) &           # not cream/white
    ~is_blue                 # not the blue runner
)

# Dilate the wood mask slightly to catch edge pixels
from PIL import ImageFilter as IF
wood_img = Image.fromarray((wood * 255).astype(np.uint8), mode='L')
# Slight dilation via max filter
wood_img = wood_img.filter(IF.MaxFilter(3))
wood_mask = np.array(wood_img) > 128

# Build the frame layer
frame = data.copy()
frame[~wood_mask, 3] = 0  # zero alpha for non-wood pixels

# Soften edges slightly
frame_img = Image.fromarray(frame)
alpha_ch = frame_img.split()[3]
alpha_ch = alpha_ch.filter(ImageFilter.GaussianBlur(radius=0.7))
frame_img.putalpha(alpha_ch)

out_path = os.path.join(OUT, "bed_frame.png")
frame_img.save(out_path)
kb = os.path.getsize(out_path) / 1024
px = np.sum(np.array(frame_img)[:,:,3] > 10)
print(f"bed_frame: {px} pixels, {kb:.0f} KB")
print("✅ Done — bed_frame.png (wood only) + bed.png (full dressed bed)")
