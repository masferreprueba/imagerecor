import zipfile
from pathlib import Path
import pytest
from app.config import Settings
from app.security import UnsafeArchive, inspect_zip


def test_rejects_zip_slip(tmp_path: Path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../escape.png", b"not-an-image")
    with pytest.raises(UnsafeArchive):
        inspect_zip(archive, Settings())
