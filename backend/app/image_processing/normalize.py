from pathlib import Path
from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps


def compose_product_template(
    source: Path,
    template_source: Path,
    destination: Path,
    zoom: float = 1.15,
) -> None:
    """Place the product, then enhance its visible area without altering the overlay."""
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

    with Image.open(template_source) as opened_template:
        template = opened_template.convert("RGBA")
    if template.size != (500, 500):
        product.close(); template.close()
        raise ValueError("La plantilla debe medir exactamente 500 × 500 px.")

    template_alpha = template.getchannel("A")
    window_mask = ImageOps.invert(template_alpha)
    window_bbox = window_mask.getbbox()
    template_alpha.close()
    if not window_bbox:
        product.close(); template.close(); window_mask.close()
        raise ValueError("La plantilla no contiene un área transparente.")

    window_width = window_bbox[2] - window_bbox[0]
    window_height = window_bbox[3] - window_bbox[1]
    ratio = min(window_width / product.width, window_height / product.height) * zoom
    dimensions = (max(1, round(product.width * ratio)), max(1, round(product.height * ratio)))
    product = product.resize(dimensions, Image.Resampling.LANCZOS)

    x = round(window_bbox[0] + (window_width - product.width) / 2)
    y = round(window_bbox[1] + (window_height - product.height) / 2)
    product_layer = Image.new("RGBA", (500, 500), (0, 0, 0, 0))
    product_layer.alpha_composite(product, (x, y))
    layer_alpha = product_layer.getchannel("A")
    clipped_alpha = ImageChops.multiply(layer_alpha, window_mask)
    product_layer.putalpha(clipped_alpha)

    composition = Image.new("RGBA", (500, 500), "white")
    composition.alpha_composite(product_layer)
    composition.alpha_composite(template)

    # The photographic correction happens after composition. It is blended only
    # through the transparent template window, so logos, copy, frames and other
    # opaque template pixels keep their original appearance and position.
    base = composition.convert("RGB")
    enhanced = base
    if min(product.size) >= 80:
        enhanced = enhanced.filter(ImageFilter.MedianFilter(3))
    enhanced = ImageEnhance.Contrast(enhanced).enhance(1.035)
    enhanced = ImageEnhance.Color(enhanced).enhance(1.01)
    enhanced = enhanced.filter(ImageFilter.UnsharpMask(radius=1.2, percent=110, threshold=3))
    result = Image.composite(enhanced, base, window_mask)
    destination.parent.mkdir(parents=True, exist_ok=True)
    result.save(destination, "JPEG", quality=97, subsampling=0, optimize=True, progressive=True)

    product.close()
    template.close(); window_mask.close(); product_layer.close(); layer_alpha.close()
    clipped_alpha.close(); composition.close(); base.close(); enhanced.close(); result.close()


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
        ratio = min(max_side / product.width, max_side / product.height)
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
    ratio = min(max_side / product.width, max_side / product.height)
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
