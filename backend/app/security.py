import shutil
import zipfile
from pathlib import Path, PurePosixPath
from PIL import Image, UnidentifiedImageError
from .config import Settings

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class UnsafeArchive(ValueError):
    pass


def inspect_zip(archive_path: Path, settings: Settings) -> list[zipfile.ZipInfo]:
    try:
        archive = zipfile.ZipFile(archive_path)
    except zipfile.BadZipFile as exc:
        raise UnsafeArchive("El archivo no es un ZIP válido.") from exc
    with archive:
        infos = [item for item in archive.infolist() if not item.is_dir()]
        if len(infos) > settings.max_files_per_zip:
            raise UnsafeArchive(f"El ZIP supera el límite de {settings.max_files_per_zip} archivos.")
        total = 0
        images: list[zipfile.ZipInfo] = []
        for item in infos:
            path = PurePosixPath(item.filename.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts:
                raise UnsafeArchive("El ZIP contiene una ruta no permitida.")
            total += item.file_size
            ratio = item.file_size / max(item.compress_size, 1)
            if ratio > settings.max_compression_ratio:
                raise UnsafeArchive("El ZIP contiene un archivo con compresión sospechosa.")
            if path.suffix.lower() in ALLOWED_EXTENSIONS:
                images.append(item)
        if total > settings.max_uncompressed_mb * 1024 * 1024:
            raise UnsafeArchive("El contenido descomprimido supera el límite permitido.")
        if not images:
            raise UnsafeArchive("No se encontraron imágenes JPG, JPEG, PNG o WEBP.")
        return images


def safe_extract_images(archive_path: Path, output_dir: Path, settings: Settings) -> list[Path]:
    infos = inspect_zip(archive_path, settings)
    output_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    used_names: set[str] = set()
    with zipfile.ZipFile(archive_path) as archive:
        for index, info in enumerate(infos, start=1):
            original = PurePosixPath(info.filename).name
            stem = Path(original).stem[:100] or f"imagen_{index}"
            suffix = Path(original).suffix.lower()
            candidate = f"{stem}{suffix}"
            serial = 2
            while candidate.lower() in used_names:
                candidate = f"{stem}_{serial}{suffix}"; serial += 1
            used_names.add(candidate.lower())
            target = output_dir / candidate
            with archive.open(info) as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination, length=1024 * 1024)
            try:
                with Image.open(target) as image:
                    image.verify()
            except (UnidentifiedImageError, OSError) as exc:
                target.unlink(missing_ok=True)
                raise UnsafeArchive(f"{original} no es una imagen válida.") from exc
            extracted.append(target)
    return extracted
