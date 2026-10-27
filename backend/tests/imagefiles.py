"""テスト用の画像のバイト列を作る。"""

import io
import random

from PIL import Image


def make_image(fmt: str = "JPEG", size: tuple[int, int] = (640, 360), *, exif: bool = False, text_chunk: bool = False, seed: int = 1) -> bytes:
    rnd = random.Random(seed)
    img = Image.new("RGB", size)
    img.putdata([(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256)) for _ in range(size[0] * size[1])]) if size[0] * size[1] < 5000 else None
    # 大きい画像は、ランダムな色の帯を重ねる（1 画素ずつは遅いので）
    if size[0] * size[1] >= 5000:
        for y in range(0, size[1], 8):
            img.paste((rnd.randrange(256), rnd.randrange(256), rnd.randrange(256)), (0, y, size[0], min(size[1], y + 8)))
    out = io.BytesIO()
    kwargs = {}
    if exif:
        e = Image.Exif()
        e[0x010F] = "SecretCamera"  # Make
        e[0x8825] = {1: "N", 2: (35.0, 41.0, 0.0)}  # GPS
        kwargs["exif"] = e
    if text_chunk and fmt == "PNG":
        from PIL import PngImagePlugin

        info = PngImagePlugin.PngInfo()
        info.add_text("Author", "secret-author")
        kwargs["pnginfo"] = info
    img.save(out, fmt, **kwargs)
    return out.getvalue()


def make_animated_png() -> bytes:
    frames = [Image.new("RGB", (300, 300), c) for c in ("red", "blue")]
    out = io.BytesIO()
    frames[0].save(out, "PNG", save_all=True, append_images=frames[1:], duration=100, loop=0)
    return out.getvalue()


def make_noise_png(size: tuple[int, int] = (300, 300)) -> bytes:
    """圧縮しても大きい PNG（容量の上限のテスト用）。"""
    import os

    out = io.BytesIO()
    Image.frombytes("RGB", size, os.urandom(size[0] * size[1] * 3)).save(out, "PNG")
    return out.getvalue()
