"""Tray icon rendering.  Pillow draws a simple eye+pause glyph so no binary
asset needs to be committed."""
from __future__ import annotations

from PIL import Image, ImageDraw


def create_icon(size: int = 64) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    inset = size // 8
    oval = (inset, size // 3, size - inset, 2 * size // 3)
    draw.ellipse(oval, outline=(56, 189, 248, 255), width=max(1, size // 16))
    pupil = size // 4
    draw.ellipse(
        (size // 2 - pupil // 2, size // 2 - pupil // 2, size // 2 + pupil // 2, size // 2 + pupil // 2),
        fill=(56, 189, 248, 255),
    )
    bar = size // 12
    draw.rectangle(
        (size // 2 - bar * 2, size // 2 - bar // 2, size // 2 - bar, size // 2 + bar // 2),
        fill=(148, 163, 184, 255),
    )
    draw.rectangle(
        (size // 2 + bar, size // 2 - bar // 2, size // 2 + bar * 2, size // 2 + bar // 2),
        fill=(148, 163, 184, 255),
    )
    return image
