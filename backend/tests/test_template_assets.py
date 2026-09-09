from io import BytesIO
from pathlib import Path

from PIL import Image

from app.template_assets import clean_template_name, load_template_metadata, save_job_template


def png_bytes(size=(500, 500), transparent=True):
    image = Image.new("RGBA", size, (255, 255, 255, 255))
    if transparent:
        image.paste((0, 0, 0, 0), (100, 100, 400, 400))
    buffer = BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def test_clean_template_name_matches_zip_contract():
    assert clean_template_name("Plantilla Ferretería Naranja") == "Plantilla_Ferreteria_Naranja"


def test_save_job_template_validates_and_persists_metadata(tmp_path: Path):
    metadata = save_job_template(png_bytes(), "Plantilla Ferretería Naranja", tmp_path)
    assert metadata["base_name"] == "Plantilla_Ferreteria_Naranja"
    assert (tmp_path / "template.png").is_file()
    assert load_template_metadata(tmp_path) == metadata
