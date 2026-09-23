import json
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from .celery_app import celery_app
from ..config import get_settings
from ..database import update_job
from ..api_credentials import active_provider_keys, record_api_attempt
from ..image_processing import create_studio_product, normalize_product
from ..security import safe_extract_images
from ..services import create_mixed_provider_chain
from ..google_drive import upload_png_folder


def _process_one(
    source: Path, cutouts: Path, png_outputs: Path, jpeg_outputs: Path,
    studio_outputs: Path, provider, output_mode: str,
) -> tuple[str, bool, str | None]:
    try:
        cutout = cutouts / f"{source.stem}.png"
        png_output = png_outputs / f"{source.stem}.png"
        provider.remove_background(source, cutout)
        settings = get_settings()
        high_resolution = output_mode == "png_4000"
        jpeg_output = None if high_resolution else jpeg_outputs / f"{source.stem}.jpg"
        normalize_product(
            cutout,
            png_output,
            4000 if high_resolution else settings.output_size,
            settings.object_margin_percent,
            jpeg_destination=jpeg_output,
        )
        if not high_resolution:
            create_studio_product(cutout, studio_outputs / f"{source.stem}_estudio.jpg")
        return source.name, True, None
    except Exception as exc:
        return source.name, False, str(exc)


def process_job(job_id: str) -> None:
    settings = get_settings()
    root = settings.storage_root / job_id
    originals = root / "originals"
    cutouts = root / "cutouts"
    png_outputs = root / "outputs"
    jpeg_outputs = root / "outputs_jpeg"
    studio_outputs = root / "outputs_studio"
    try:
        from ..database import JobRecord, SessionLocal
        with SessionLocal() as session:
            record = session.get(JobRecord, job_id)
            output_mode = record.output_mode if record else "standard"
            zip_filename = record.filename if record else "Imagenes.zip"
        update_job(job_id, status="extracting", error=None)
        images = safe_extract_images(root / "input.zip", originals, settings)
        update_job(job_id, status="processing", total_images=len(images))
        cutouts.mkdir(parents=True, exist_ok=True)
        png_outputs.mkdir(parents=True, exist_ok=True)
        jpeg_outputs.mkdir(parents=True, exist_ok=True)
        studio_outputs.mkdir(parents=True, exist_ok=True)
        credentials = active_provider_keys()
        provider = create_mixed_provider_chain(
            credentials,
            settings.image_api_timeout,
            settings.image_api_max_retries,
            on_attempt=lambda credential_id, success, error: record_api_attempt(credential_id, success, error, job_id),
            local_enabled=settings.local_background_removal_enabled,
            local_model=settings.local_background_removal_model,
            local_max_side=settings.local_background_removal_max_side,
        )
        processed = failed = 0
        failures: list[dict[str, str]] = []
        with ThreadPoolExecutor(max_workers=settings.processing_concurrency) as pool:
            futures = [pool.submit(_process_one, image, cutouts, png_outputs, jpeg_outputs, studio_outputs, provider, output_mode) for image in images]
            for future in as_completed(futures):
                name, ok, error = future.result()
                if ok: processed += 1
                else:
                    failed += 1; failures.append({"file": name, "error": error or "Error desconocido"})
                update_job(job_id, processed_images=processed, failed_images=failed)
        if processed == 0:
            detail = failures[0]["error"] if failures else "Error desconocido."
            raise RuntimeError(f"Ninguna imagen pudo procesarse. {detail}")
        if failures:
            error_report = json.dumps(failures, ensure_ascii=False, indent=2)
            (png_outputs / "errores.json").write_text(error_report, encoding="utf-8")
            if output_mode == "standard":
                (jpeg_outputs / "errores.json").write_text(error_report, encoding="utf-8")
                (studio_outputs / "errores.json").write_text(error_report, encoding="utf-8")
        update_job(job_id, status="packaging")
        png_archive = Path(shutil.make_archive(str(root / "imagenes_png_sin_fondo"), "zip", png_outputs))
        if output_mode == "standard":
            shutil.make_archive(str(root / "imagenes_jpeg_fondo_blanco"), "zip", jpeg_outputs)
            shutil.make_archive(str(root / "imagenes_jpeg_calidad_estudio"), "zip", studio_outputs)
        else:
            if settings.google_drive_enabled:
                try:
                    drive_url = upload_png_folder(settings, zip_filename, png_outputs)
                    update_job(job_id, drive_status="completed", drive_folder_url=drive_url, drive_error=None)
                except Exception as drive_exc:
                    update_job(job_id, drive_status="failed", drive_error=str(drive_exc)[:2000])
            else:
                update_job(job_id, drive_status="disabled", drive_error="Google Drive no está habilitado en Render.")
        update_job(job_id, status="completed", output_path=str(png_archive))
        shutil.rmtree(cutouts, ignore_errors=True)
    except Exception as exc:
        update_job(job_id, status="failed", error=str(exc)[:2000])


@celery_app.task(name="app.workers.process_job")
def process_job_task(job_id: str) -> None:
    process_job(job_id)
