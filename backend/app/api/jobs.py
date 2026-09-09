import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from ..config import get_settings
from ..auth import require_auth
from ..database import JobRecord, SessionLocal
from ..progress import calculate_progress
from ..schemas import JobResponse, Preview
from ..security import UnsafeArchive, inspect_zip
from ..workers.tasks import process_job, process_job_task
from ..template_assets import load_template_metadata, save_job_template

router = APIRouter(prefix="/api/jobs", tags=["jobs"], dependencies=[Depends(require_auth)])
settings = get_settings()
# Render Free has limited memory. Running more than one ZIP job at once can
# exhaust it when PhotoRoom returns large transparent images.
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="job")


def serialize(record: JobRecord) -> JobResponse:
    total = max(record.total_images, 0)
    progress = calculate_progress(
        record.status,
        total,
        record.processed_images,
        record.failed_images,
    )
    previews: list[Preview] = []
    root = settings.storage_root / record.id
    originals = root / "originals"
    final_images = sorted((root / "outputs_template").glob("*.jpg"))
    if originals.exists():
        for index, source in enumerate(sorted(originals.iterdir())[:6]):
            output = final_images[index] if index < len(final_images) else None
            previews.append(Preview(
                name=source.name, status="completed" if output else "processing",
                original_url=f"/api/jobs/{record.id}/files/original/{source.name}",
                processed_url=f"/api/jobs/{record.id}/files/processed/{output.name}" if output else None,
            ))
    return JobResponse(
        id=record.id, filename=record.filename, provider=record.provider, status=record.status,
        total_images=record.total_images, processed_images=record.processed_images,
        failed_images=record.failed_images, progress=progress, error=record.error,
        download_url=f"/api/jobs/{record.id}/download/template" if record.status == "completed" else None,
        download_png_url=None,
        download_jpeg_url=None,
        download_studio_url=None,
        download_template_url=f"/api/jobs/{record.id}/download/template" if record.status == "completed" else None,
        previews=previews, created_at=record.created_at,
    )


@router.post("", response_model=JobResponse, status_code=202)
def create_job(
    file: UploadFile = File(...),
    template: UploadFile = File(...),
    template_name: str = Form(...),
    x_user_id: str | None = Header(default=None),
):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(415, "Solo se aceptan archivos ZIP.")
    job_id = str(uuid.uuid4())
    root = settings.storage_root / job_id
    root.mkdir(parents=True, exist_ok=False)
    archive = root / "input.zip"
    try:
        if not template.filename or not template.filename.lower().endswith(".png"):
            raise HTTPException(415, "La plantilla debe ser un archivo PNG.")
        try:
            save_job_template(template.file.read(15 * 1024 * 1024 + 1), template_name, root)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        max_bytes = settings.max_upload_mb * 1024 * 1024
        total = 0
        with archive.open("wb") as destination:
            while chunk := file.file.read(1024 * 1024):
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(413, f"El ZIP supera el límite de {settings.max_upload_mb} MB.")
                destination.write(chunk)
        images = inspect_zip(archive, settings)
        with SessionLocal.begin() as session:
            record = JobRecord(id=job_id, user_id=x_user_id, filename=Path(file.filename).name[:255], provider=settings.image_api_provider, status="queued", total_images=len(images))
            session.add(record)
        if settings.task_queue.lower() == "celery":
            process_job_task.delay(job_id)
        else:
            executor.submit(process_job, job_id)
        return serialize(record)
    except UnsafeArchive as exc:
        shutil.rmtree(root, ignore_errors=True)
        raise HTTPException(400, str(exc)) from exc
    except HTTPException:
        shutil.rmtree(root, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(root, ignore_errors=True)
        raise HTTPException(500, "No fue posible registrar el proceso.") from exc


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str):
    with SessionLocal() as session:
        record = session.scalar(select(JobRecord).where(JobRecord.id == job_id))
        if not record: raise HTTPException(404, "Proceso no encontrado.")
        return serialize(record)


@router.get("/{job_id}/images")
def list_processed_images(job_id: str):
    with SessionLocal() as session:
        record = session.get(JobRecord, job_id)
        if not record or record.status != "completed":
            raise HTTPException(404, "Las imágenes procesadas todavía no están disponibles.")
    output_dir = settings.storage_root / job_id / "outputs_template"
    if not output_dir.is_dir():
        raise HTTPException(410, "Las imágenes de este proceso ya expiraron.")
    images = [
        {"name": path.name, "url": f"/api/jobs/{job_id}/files/processed/{quote(path.name)}"}
        for path in sorted(output_dir.iterdir())
        if path.is_file() and path.suffix.lower() == ".jpg"
    ]
    return {"images": images}


@router.get("/{job_id}/download")
def download_job(job_id: str):
    return download_job_format(job_id, "template")


@router.get("/{job_id}/download/{output_format}")
def download_job_format(job_id: str, output_format: str):
    if output_format != "template":
        raise HTTPException(400, "Formato de descarga no permitido.")
    with SessionLocal() as session:
        record = session.get(JobRecord, job_id)
        if not record or record.status != "completed" or not record.output_path:
            raise HTTPException(404, "El ZIP final todavía no está disponible.")
        metadata = load_template_metadata(settings.storage_root / job_id)
        path = settings.storage_root / job_id / f"{metadata['base_name']}.zip"
        if not path.is_file(): raise HTTPException(410, "El archivo ya expiró.")
        return FileResponse(path, media_type="application/zip", filename=f"{metadata['base_name']}.zip")


@router.get("/{job_id}/files/{kind}/{filename}")
def job_file(job_id: str, kind: str, filename: str):
    if kind not in {"original", "processed"} or Path(filename).name != filename:
        raise HTTPException(400, "Ruta no permitida.")
    folder = "originals" if kind == "original" else "outputs_template"
    path = settings.storage_root / job_id / folder / filename
    if not path.is_file(): raise HTTPException(404, "Imagen no encontrada.")
    return FileResponse(path)
