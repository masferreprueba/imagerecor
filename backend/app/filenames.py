from pathlib import Path


def normalize_zip_filename(filename: str) -> str:
    """Preserve the uploaded ZIP name while making it safe for download headers."""
    basename = Path(filename.replace("\\", "/")).name
    cleaned = "".join(character for character in basename if character >= " " and character != "\x7f").strip()
    if not cleaned.lower().endswith(".zip"):
        raise ValueError("Solo se aceptan archivos ZIP.")
    if len(cleaned) > 255:
        stem = Path(cleaned).stem[:251].rstrip(" .") or "imagenes"
        cleaned = f"{stem}.zip"
    return cleaned
