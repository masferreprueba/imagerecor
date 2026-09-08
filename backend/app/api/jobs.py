import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from ..config import get_settings
from ..database import JobRecord, SessionLocal
from ..schemas import JobResponse, Preview
from ..security import UnsafeArchive, inspect_zip
from ..workers.tasks import process_job, process_job_task

router = APIRouter(prefix="/api/jobs", tags=["jobs"])
settings = get_settings()
executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="job")


def serialize(record: JobRecord) -> JobResponse:
    total = max(record.total_images, 0)
    done = record.processed_images + record.failed_images
    progress = 100.0 if record.status == "completed" else round(done / total * 100, 1) if total else 0.0
    previews: list[Preview] = []
    root = settings.storage_root / record.id
    originals = root / "originals"
    if originals.exists():
        for source in sorted(originals.iterdir())[:6]:
            output = root / "outputs" / f"{source.stem}.png"
            previews.append(Preview(
                name=source.name, status="completed" if output.exists() else "processing",
                original_url=f"/api/jobs/{record.id}/files/original/{source.name}",
                processed_url=f"/api/jobs/{record.id}/files/processed/{output.name}" if output.exists() else None,
            ))
    return JobResponse(
        id=record.id, filename=record.filename, provider=record.provider, status=record.status,
        total_images=record.total_images, processed_images=record.processed_images,
        failed_images=record.failed_images, progress=progress, error=record.error,
        download_url=f"/api/jobs/{record.id}/download" if record.status == "completed" else None,
        previews=previews, created_at=record.created_at,
    )


@router.post("", response_model=JobResponse, status_code=202)
def create_job(file: UploadFile = File(...), x_user_id: str | None = Header(default=None)):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(415, "Solo se aceptan archivos ZIP.")
    job_id = str(uuid.uuid4())
    root = settings.storage_root / job_id
    root.mkdir(parents=True, exist_ok=False)
    archive = root / "input.zip"
    try:
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


@router.get("/{job_id}/download")
def download_job(job_id: str):
    with SessionLocal() as session:
        record = session.get(JobRecord, job_id)
        if not record or record.status != "completed" or not record.output_path:
            raise HTTPException(404, "El ZIP final todavía no está disponible.")
        path = Path(record.output_path)
        if not path.is_file(): raise HTTPException(410, "El archivo ya expiró.")
        return FileResponse(path, media_type="application/zip", filename=f"{Path(record.filename).stem}_procesado.zip")


@router.get("/{job_id}/files/{kind}/{filename}")
def job_file(job_id: str, kind: str, filename: str):
    if kind not in {"original", "processed"} or Path(filename).name != filename:
        raise HTTPException(400, "Ruta no permitida.")
    folder = "originals" if kind == "original" else "outputs"
    path = settings.storage_root / job_id / folder / filename
    if not path.is_file(): raise HTTPException(404, "Imagen no encontrada.")
    return FileResponse(path)
