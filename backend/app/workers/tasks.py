import json
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from .celery_app import celery_app
from ..config import get_settings
from ..database import update_job
from ..api_credentials import active_provider_keys, record_api_attempt
from ..image_processing import normalize_product
from ..security import safe_extract_images
from ..services import create_mixed_provider_chain


def _process_one(source: Path, cutouts: Path, png_outputs: Path, jpeg_outputs: Path, provider) -> tuple[str, bool, str | None]:
    try:
        cutout = cutouts / f"{source.stem}.png"
        png_output = png_outputs / f"{source.stem}.png"
        jpeg_output = jpeg_outputs / f"{source.stem}.jpg"
        provider.remove_background(source, cutout)
        settings = get_settings()
        normalize_product(
            cutout,
            png_output,
            settings.output_size,
            settings.object_margin_percent,
            jpeg_destination=jpeg_output,
        )
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
    try:
        update_job(job_id, status="processing", error=None)
        images = safe_extract_images(root / "input.zip", originals, settings)
        update_job(job_id, total_images=len(images))
        cutouts.mkdir(parents=True, exist_ok=True)
        png_outputs.mkdir(parents=True, exist_ok=True)
        jpeg_outputs.mkdir(parents=True, exist_ok=True)
        credentials = active_provider_keys()
        provider = create_mixed_provider_chain(
            credentials,
            settings.image_api_timeout,
            settings.image_api_max_retries,
            on_attempt=lambda credential_id, success, error: record_api_attempt(credential_id, success, error, job_id),
        )
        processed = failed = 0
        failures: list[dict[str, str]] = []
        with ThreadPoolExecutor(max_workers=settings.processing_concurrency) as pool:
            futures = [pool.submit(_process_one, image, cutouts, png_outputs, jpeg_outputs, provider) for image in images]
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
            (jpeg_outputs / "errores.json").write_text(error_report, encoding="utf-8")
        png_archive = Path(shutil.make_archive(str(root / "imagenes_png_sin_fondo"), "zip", png_outputs))
        shutil.make_archive(str(root / "imagenes_jpeg_fondo_blanco"), "zip", jpeg_outputs)
        update_job(job_id, status="completed", output_path=str(png_archive))
        shutil.rmtree(cutouts, ignore_errors=True)
    except Exception as exc:
        update_job(job_id, status="failed", error=str(exc)[:2000])


@celery_app.task(name="app.workers.process_job")
def process_job_task(job_id: str) -> None:
    process_job(job_id)
