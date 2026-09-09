from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter

VISUAL_SCALE = 1.25


def normalize_product(
    source: Path,
    destination: Path,
    size: int = 500,
    margin_percent: int = 10,
    jpeg_destination: Path | None = None,
) -> None:
    with Image.open(source) as opened:
        image = opened.convert("RGBA")
        alpha = image.getchannel("A")
        bbox = alpha.getbbox()
        if not bbox:
            raise ValueError("La imagen procesada no contiene un objeto visible.")
        product = image.crop(bbox)
        alpha.close()
        image.close()
        max_side = max(1, round(size * (1 - 2 * margin_percent / 100)))
        # Grow uniformly from the center while preserving the 500 × 500 canvas.
        ratio = min(max_side / product.width, max_side / product.height) * VISUAL_SCALE
        dimensions = (max(1, round(product.width * ratio)), max(1, round(product.height * ratio)))
        resized = product.resize(dimensions, Image.Resampling.LANCZOS)
        product.close()
        product = resized
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        position = ((size - product.width) // 2, (size - product.height) // 2)
        canvas.alpha_composite(product, position)
        product.close()
        destination.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(destination, "PNG", optimize=True, compress_level=9)
        if jpeg_destination:
            jpeg_destination.parent.mkdir(parents=True, exist_ok=True)
            white = Image.new("RGB", (size, size), "white")
            white.paste(canvas, mask=canvas.getchannel("A"))
            white.save(jpeg_destination, "JPEG", quality=95, optimize=True, progressive=True)


def create_studio_product(
    source: Path,
    destination: Path,
    size: int = 1500,
    margin_percent: int = 12,
) -> None:
    """Create a conservative studio-style JPEG without regenerating the product.

    The product pixels remain a separate foreground layer. Only mild photographic
    corrections are applied; the background and shadow are synthesized from its
    real alpha mask so labels, logos and geometry are not redrawn.
    """
    with Image.open(source) as opened:
        image = opened.convert("RGBA")
        alpha = image.getchannel("A")
        bbox = alpha.getbbox()
        alpha.close()
        if not bbox:
            image.close()
            raise ValueError("La imagen procesada no contiene un objeto visible.")
        product = image.crop(bbox)
        image.close()

    max_side = max(1, round(size * (1 - 2 * margin_percent / 100)))
    ratio = min(max_side / product.width, max_side / product.height) * VISUAL_SCALE
    dimensions = (
        max(1, round(product.width * ratio)),
        max(1, round(product.height * ratio)),
    )
    product = product.resize(dimensions, Image.Resampling.LANCZOS)

    product_alpha = product.getchannel("A")
    rgb = product.convert("RGB")
    # Restrained adjustments emulate a clean product-photo finish while keeping
    # colors and small printed details recognizable.
    rgb = ImageEnhance.Contrast(rgb).enhance(1.04)
    rgb = ImageEnhance.Color(rgb).enhance(1.02)
    rgb = ImageEnhance.Sharpness(rgb).enhance(1.12)
    enhanced = rgb.convert("RGBA")
    enhanced.putalpha(product_alpha)
    rgb.close()

    # Neutral vertical gradient: white above, subtly darker at the table line.
    gradient = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / max(1, size - 1)
        value = round(255 - 11 * (t ** 1.7))
        gradient.putpixel((0, y), (value, value, min(255, value + 1)))
    background = gradient.resize((size, size))
    gradient.close()

    x = (size - enhanced.width) // 2
    y = max(0, (size - enhanced.height) // 2 - round(size * 0.015))

    # A blurred copy of the true alpha creates a natural contact shadow.
    shadow_alpha = Image.new("L", (size, size), 0)
    shadow_alpha.paste(product_alpha, (x, min(size - enhanced.height, y + round(size * 0.022))))
    shadow_alpha = shadow_alpha.filter(ImageFilter.GaussianBlur(max(8, round(size * 0.018))))
    shadow_alpha = shadow_alpha.point(lambda value: round(value * 0.20))
    shadow = Image.new("RGBA", (size, size), (30, 38, 36, 0))
    shadow.putalpha(shadow_alpha)

    composed = background.convert("RGBA")
    composed.alpha_composite(shadow)
    composed.alpha_composite(enhanced, (x, y))

    destination.parent.mkdir(parents=True, exist_ok=True)
    composed.convert("RGB").save(
        destination,
        "JPEG",
        quality=95,
        optimize=True,
        progressive=True,
        subsampling=0,
    )

    product.close()
    product_alpha.close()
    enhanced.close()
    background.close()
    shadow_alpha.close()
    shadow.close()
    composed.close()
