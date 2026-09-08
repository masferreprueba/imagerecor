from pathlib import Path
from PIL import Image
from app.image_processing.normalize import normalize_product


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
