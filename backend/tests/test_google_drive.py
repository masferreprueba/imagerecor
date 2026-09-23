from app.google_drive import folder_name_from_zip


def test_folder_name_preserves_zip_name():
    assert folder_name_from_zip("Catálogo Ferretería.zip") == "Catálogo Ferretería"


def test_folder_name_strips_client_path():
    assert folder_name_from_zip(r"C:\\fotos\\Taladros.zip") == "Taladros"
