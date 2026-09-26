import shutil
from pathlib import Path

from PIL import Image

from app.workers.tasks import _process_one


class CopyProvider:
    def remove_background(self, source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def test_standard_job_also_generates_4000_png(tmp_path: Path):
    source = tmp_path / "product.png"
    with Image.new("RGBA", (80, 120), (220, 30, 20, 255)) as image:
        image.save(source)

    folders = {
        name: tmp_path / name
        for name in ("cutouts", "png", "jpeg", "studio", "highres")
    }

    name, ok, error = _process_one(
        source,
        folders["cutouts"],
        folders["png"],
        folders["jpeg"],
        folders["studio"],
        folders["highres"],
        CopyProvider(),
        "standard",
    )

    assert (name, ok, error) == ("product.png", True, None)
    with Image.open(folders["png"] / "product.png") as standard:
        assert standard.size == (500, 500)
    with Image.open(folders["highres"] / "product.png") as highres:
        assert highres.size == (4000, 4000)
