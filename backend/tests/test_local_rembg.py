import io
import sys
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from app.services.local_rembg_service import LocalRembgProvider


def test_local_rembg_writes_transparent_png(tmp_path: Path, monkeypatch):
    source = tmp_path / "source.jpg"
    destination = tmp_path / "result.png"
    Image.new("RGB", (20, 20), "white").save(source)

    output = io.BytesIO()
    cutout = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
    cutout.paste((255, 0, 0, 255), (5, 5, 15, 15))
    cutout.save(output, "PNG")

    calls = {}

    def new_session(model):
        calls["model"] = model
        return object()

    def remove(data, session, decontaminate):
        calls["decontaminate"] = decontaminate
        return output.getvalue()

    monkeypatch.setitem(sys.modules, "rembg", SimpleNamespace(new_session=new_session, remove=remove))
    LocalRembgProvider("silueta").remove_background(source, destination)

    assert calls == {"model": "silueta", "decontaminate": True}
    with Image.open(destination) as result:
        assert result.mode == "RGBA"
        assert result.getchannel("A").getbbox() == (5, 5, 15, 15)


def test_local_rembg_limits_large_inference_input(tmp_path: Path):
    source = tmp_path / "large.jpg"
    Image.new("RGB", (4000, 3000), "white").save(source)

    prepared = LocalRembgProvider("silueta", max_side=1600)._prepare_input(source)

    with Image.open(io.BytesIO(prepared)) as image:
        assert image.size == (1600, 1200)
