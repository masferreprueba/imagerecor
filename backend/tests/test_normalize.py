from pathlib import Path
from PIL import Image
from app.image_processing.normalize import compose_product_template, create_studio_product, normalize_product


def test_normalize_centers_visible_object(tmp_path: Path):
    source = tmp_path / "source.png"
    output = tmp_path / "output.png"
    image = Image.new("RGBA", (200, 100), (0, 0, 0, 0))
    image.paste((255, 0, 0, 255), (25, 25, 175, 75))
    image.save(source)
    normalize_product(source, output, size=500, margin_percent=10)
    result = Image.open(output)
    assert result.size == (500, 500)
    assert result.mode == "RGBA"
    assert result.getchannel("A").getbbox() == (50, 183, 450, 316)


def test_normalize_creates_white_background_jpeg(tmp_path: Path):
    source = tmp_path / "source.png"
    png_output = tmp_path / "output.png"
    jpeg_output = tmp_path / "output.jpg"
    image = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    image.paste((255, 0, 0, 255), (25, 25, 75, 75))
    image.save(source)

    normalize_product(source, png_output, jpeg_destination=jpeg_output)

    result = Image.open(jpeg_output)
    assert result.size == (500, 500)
    assert result.mode == "RGB"
    corner = result.getpixel((0, 0))
    assert all(channel >= 250 for channel in corner)


def test_create_studio_product_creates_large_jpeg_with_neutral_background(tmp_path: Path):
    source = tmp_path / "source.png"
    output = tmp_path / "studio.jpg"
    image = Image.new("RGBA", (120, 80), (0, 0, 0, 0))
    image.paste((210, 35, 30, 255), (20, 10, 100, 70))
    image.save(source)

    create_studio_product(source, output)

    result = Image.open(output)
    assert result.size == (1500, 1500)
    assert result.mode == "RGB"
    assert all(channel >= 240 for channel in result.getpixel((0, 0)))
    center = result.getpixel((750, 750))
    assert center[0] > center[1] * 2


def test_template_composition_preserves_overlay_and_size(tmp_path: Path):
    source = tmp_path / "product.png"
    template = tmp_path / "template.png"
    output = tmp_path / "final.jpg"
    product = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    product.paste((220, 30, 20, 255), (25, 25, 75, 75))
    product.save(source)
    overlay = Image.new("RGBA", (500, 500), (10, 40, 80, 255))
    overlay.paste((0, 0, 0, 0), (100, 100, 400, 400))
    overlay.save(template)

    compose_product_template(source, template, output)

    with Image.open(output) as result:
        assert result.size == (500, 500)
        corner = result.convert("RGB").getpixel((10, 10))
        assert all(abs(actual - expected) <= 8 for actual, expected in zip(corner, (10, 40, 80)))
        assert result.getpixel((250, 250))[0] > 150
