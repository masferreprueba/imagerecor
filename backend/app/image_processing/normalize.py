from pathlib import Path
from PIL import Image


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
        max_side = max(1, round(size * (1 - 2 * margin_percent / 100)))
        ratio = min(max_side / product.width, max_side / product.height)
        dimensions = (max(1, round(product.width * ratio)), max(1, round(product.height * ratio)))
        product = product.resize(dimensions, Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        position = ((size - product.width) // 2, (size - product.height) // 2)
        canvas.alpha_composite(product, position)
        destination.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(destination, "PNG", optimize=True, compress_level=9)
        if jpeg_destination:
            jpeg_destination.parent.mkdir(parents=True, exist_ok=True)
            white = Image.new("RGB", (size, size), "white")
            white.paste(canvas, mask=canvas.getchannel("A"))
            white.save(jpeg_destination, "JPEG", quality=95, optimize=True, progressive=True)
