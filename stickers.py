"""Built-in stickers, drawn with Pillow so no extra image files are needed.

Each sticker is a transparent PNG. Users can also upload their own stickers,
logos or signature images in the Design step.
"""
from __future__ import annotations

import math
from io import BytesIO

from PIL import Image, ImageDraw

SIZE = 480          # final size in pixels
SS = 3              # supersampling factor for smooth edges


def _canvas():
    big = SIZE * SS
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img), big


def _finish(img: Image.Image) -> bytes:
    img = img.resize((SIZE, SIZE), Image.LANCZOS)
    out = BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


def _star(points=5, inner=0.45):
    img, d, big = _canvas()
    c = big / 2
    r_out, r_in = big * 0.46, big * 0.46 * inner
    pts = []
    for i in range(points * 2):
        r = r_out if i % 2 == 0 else r_in
        a = -math.pi / 2 + i * math.pi / points
        pts.append((c + r * math.cos(a), c + r * math.sin(a)))
    d.polygon(pts, fill=(232, 178, 32, 255), outline=(176, 124, 10, 255))
    d.line(pts + [pts[0]], fill=(176, 124, 10, 255), width=big // 60)
    return _finish(img)


def _seal(color=(184, 134, 11), ribbons=True):
    img, d, big = _canvas()
    c = big / 2
    if ribbons:
        for sign in (-1, 1):
            x = c + sign * big * 0.12
            d.polygon([(x - big * 0.09, c), (x + big * 0.09, c),
                       (x + big * 0.09 + sign * big * 0.06, big * 0.96),
                       (x, big * 0.86), (x - big * 0.09 + sign * big * 0.06, big * 0.96)],
                      fill=(150, 30, 40, 255))
    # scalloped edge
    n = 28
    r_edge = big * 0.34
    for i in range(n):
        a = 2 * math.pi * i / n
        x, y = c + r_edge * math.cos(a), c * 0.86 + r_edge * math.sin(a)
        d.ellipse([x - big * 0.045, y - big * 0.045, x + big * 0.045, y + big * 0.045],
                  fill=color + (255,))
    cy = c * 0.86
    d.ellipse([c - r_edge, cy - r_edge, c + r_edge, cy + r_edge], fill=color + (255,))
    lighter = tuple(min(255, v + 45) for v in color)
    d.ellipse([c - r_edge * 0.8, cy - r_edge * 0.8, c + r_edge * 0.8, cy + r_edge * 0.8],
              fill=lighter + (255,), outline=(255, 255, 255, 230), width=big // 90)
    # small star in the middle
    pts = []
    for i in range(10):
        r = r_edge * (0.5 if i % 2 == 0 else 0.22)
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((c + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon(pts, fill=(255, 255, 255, 240))
    return _finish(img)


def _check_badge():
    img, d, big = _canvas()
    c = big / 2
    r = big * 0.44
    d.ellipse([c - r, c - r, c + r, c + r], fill=(22, 128, 75, 255))
    d.ellipse([c - r * 0.86, c - r * 0.86, c + r * 0.86, c + r * 0.86],
              outline=(255, 255, 255, 255), width=big // 40)
    w = big // 22
    d.line([(c - r * 0.42, c + r * 0.02), (c - r * 0.1, c + r * 0.34), (c + r * 0.46, c - r * 0.3)],
           fill=(255, 255, 255, 255), width=w, joint="curve")
    return _finish(img)


def _ribbon():
    img, d, big = _canvas()
    blue = (28, 70, 150, 255)
    d.rectangle([big * 0.04, big * 0.30, big * 0.96, big * 0.62], fill=blue)
    d.polygon([(big * 0.04, big * 0.30), (big * 0.04, big * 0.62), (0, big * 0.46)], fill=(255, 255, 255, 0))
    d.polygon([(big * 0.96, big * 0.30), (big * 0.96, big * 0.62), (big, big * 0.46)], fill=(255, 255, 255, 0))
    d.rectangle([big * 0.04, big * 0.34, big * 0.96, big * 0.36], fill=(255, 255, 255, 235))
    d.rectangle([big * 0.04, big * 0.56, big * 0.96, big * 0.58], fill=(255, 255, 255, 235))
    return _finish(img)


def _medal():
    img, d, big = _canvas()
    c = big / 2
    d.polygon([(c - big * 0.22, 0), (c, big * 0.36), (c - big * 0.04, big * 0.44), (c - big * 0.34, big * 0.05)],
              fill=(176, 36, 48, 255))
    d.polygon([(c + big * 0.22, 0), (c, big * 0.36), (c + big * 0.04, big * 0.44), (c + big * 0.34, big * 0.05)],
              fill=(30, 70, 150, 255))
    cy, r = big * 0.66, big * 0.30
    d.ellipse([c - r, cy - r, c + r, cy + r], fill=(222, 170, 30, 255), outline=(150, 105, 10, 255), width=big // 60)
    d.ellipse([c - r * 0.78, cy - r * 0.78, c + r * 0.78, cy + r * 0.78], outline=(255, 240, 180, 255), width=big // 70)
    pts = []
    for i in range(10):
        rr = r * (0.52 if i % 2 == 0 else 0.22)
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((c + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=(255, 250, 225, 255))
    return _finish(img)


BUILTIN_STICKERS = {
    "b:star": ("Gold star", _star),
    "b:seal": ("Gold seal", _seal),
    "b:medal": ("Medal", _medal),
    "b:check": ("Verified badge", _check_badge),
    "b:ribbon": ("Blue ribbon", _ribbon),
}

_cache: dict[str, bytes] = {}


def builtin_sticker_bytes() -> dict[str, tuple[str, bytes]]:
    """{sticker id: (display name, PNG bytes)}"""
    if not _cache:
        for sid, (_, fn) in BUILTIN_STICKERS.items():
            _cache[sid] = fn()
    return {sid: (BUILTIN_STICKERS[sid][0], data) for sid, data in _cache.items()}


def prepare_uploaded_sticker(data: bytes, make_white_transparent: bool = False,
                             max_side: int = 900) -> bytes:
    """Clean up a user-uploaded sticker/logo/signature and return PNG bytes."""
    import numpy as np
    from PIL import ImageOps

    try:
        image = Image.open(BytesIO(data))
        image.load()
    except Exception as error:  # noqa: BLE001
        raise ValueError("this is not a readable image") from error
    image = ImageOps.exif_transpose(image).convert("RGBA")
    scale = max_side / max(image.size)
    if scale < 1:
        image = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
    if make_white_transparent:
        arr = np.asarray(image).astype(float)
        brightness = arr[..., :3].min(axis=2)           # darkest channel: white ~ 255
        alpha = np.clip((250 - brightness) / 40.0, 0, 1) * 255   # soft edge between 210 and 250
        arr[..., 3] = np.minimum(arr[..., 3], alpha)
        image = Image.fromarray(arr.astype("uint8"), "RGBA")
    out = BytesIO()
    image.save(out, "PNG", optimize=True)
    return out.getvalue()
