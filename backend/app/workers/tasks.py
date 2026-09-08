import json
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from .celery_app import celery_app
from ..config import get_settings
from ..database import update_job
from ..image_processing import normalize_product
from ..security import safe_extract_images
from ..services import create_provider


def _process_one(source: Path, cutouts: Path, outputs: Path, provider) -> tuple[str, bool, str | None]:
    try:
        cutout = cutouts / f"{source.stem}.png"
        output = outputs / f"{source.stem}.png"
        provider.remove_background(source, cutout)
        settings = get_settings()
        normalize_product(cutout, output, settings.output_size, settings.object_margin_percent)
        return source.name, True, None
    except Exception as exc:
        return source.name, False, str(exc)


def process_job(job_id: str) -> None:
    settings = get_settings()
    root = settings.storage_root / job_id
    originals, cutouts, outputs = root / "originals", root / "cutouts", root / "outputs"
    try:
        update_job(job_id, status="processing", error=None)
        images = safe_extract_images(root / "input.zip", originals, settings)
        update_job(job_id, total_images=len(images))
        cutouts.mkdir(parents=True, exist_ok=True); outputs.mkdir(parents=True, exist_ok=True)
        provider = create_provider(settings.image_api_provider, settings.image_api_key, settings.image_api_timeout, settings.image_api_max_retries)
        processed = failed = 0
        failures: list[dict[str, str]] = []
        with ThreadPoolExecutor(max_workers=settings.processing_concurrency) as pool:
            futures = [pool.submit(_process_one, image, cutouts, outputs, provider) for image in images]
            for future in as_completed(futures):
                name, ok, error = future.result()
                if ok: processed += 1
                else:
                    failed += 1; failures.append({"file": name, "error": error or "Error desconocido"})
                update_job(job_id, processed_images=processed, failed_images=failed)
        if processed == 0:
            raise RuntimeError("Ninguna imagen pudo procesarse.")
        if failures:
            (outputs / "errores.json").write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
        archive_base = root / "imagenes_procesadas"
        archive_path = Path(shutil.make_archive(str(archive_base), "zip", outputs))
        update_job(job_id, status="completed", output_path=str(archive_path))
        shutil.rmtree(cutouts, ignore_errors=True)
    except Exception as exc:
        update_job(job_id, status="failed", error=str(exc)[:2000])


@celery_app.task(name="app.workers.process_job")
def process_job_task(job_id: str) -> None:
    process_job(job_id)
