from backend.app.filenames import normalize_zip_filename


def test_preserves_original_zip_filename() -> None:
    assert normalize_zip_filename("Catálogo Ferretería 2026.zip") == "Catálogo Ferretería 2026.zip"


def test_removes_client_path_without_changing_zip_name() -> None:
    assert normalize_zip_filename(r"C:\Fotos\Taladros_Septiembre.zip") == "Taladros_Septiembre.zip"


def test_long_name_keeps_zip_extension() -> None:
    result = normalize_zip_filename(f"{'a' * 300}.zip")
    assert len(result) == 255
    assert result.endswith(".zip")
