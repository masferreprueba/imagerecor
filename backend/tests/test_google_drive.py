from app.google_drive import DRIVE_SCOPE, archive_name_from_zip, folder_name_from_zip


def test_drive_scope_is_limited_to_app_files():
    assert DRIVE_SCOPE == "https://www.googleapis.com/auth/drive.file"


def test_folder_name_preserves_zip_name():
    assert folder_name_from_zip("Catálogo Ferretería.zip") == "Catálogo Ferretería"


def test_folder_name_strips_client_path():
    assert folder_name_from_zip(r"C:\\fotos\\Taladros.zip") == "Taladros"


def test_archive_name_identifies_4000_output():
    assert archive_name_from_zip("Catálogo Ferretería.zip") == "Catálogo Ferretería - PNG 4000x4000.zip"
