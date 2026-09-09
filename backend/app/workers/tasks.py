import json
import shutil
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from .celery_app import celery_app
from ..config import get_settings
from ..database import update_job
from ..api_credentials import active_provider_keys, record_api_attempt
from ..image_processing import compose_product_template
from ..security import safe_extract_images
from ..services import create_mixed_provider_chain
from ..template_assets import load_template_metadata


def _process_one(source: Path, index: int, cutouts: Path, template_outputs: Path, template_source: Path, provider) -> tuple[str, bool, str | None]:
    try:
        cutout = cutouts / f"{source.stem}.png"
        template_output = template_outputs / f"{index:06d}.jpg"
        provider.remove_background(source, cutout)
        compose_product_template(cutout, template_source, template_output, zoom=1.15)
        return source.name, True, None
    except Exception as exc:
        return source.name, False, str(exc)


def process_job(job_id: str) -> None:
    settings = get_settings()
    root = settings.storage_root / job_id
    originals = root / "originals"
    cutouts = root / "cutouts"
    template_outputs = root / "outputs_template_work"
    template_finals = root / "outputs_template"
    try:
        update_job(job_id, status="extracting", error=None)
        images = safe_extract_images(root / "input.zip", originals, settings)
        template_metadata = load_template_metadata(root)
        template_source = root / "template.png"
        update_job(job_id, status="processing", total_images=len(images))
        cutouts.mkdir(parents=True, exist_ok=True)
        template_outputs.mkdir(parents=True, exist_ok=True)
        template_finals.mkdir(parents=True, exist_ok=True)
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
            futures = [pool.submit(_process_one, image, index, cutouts, template_outputs, template_source, provider) for index, image in enumerate(images, start=1)]
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
            (root / "errores.json").write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
        update_job(job_id, status="packaging")
        base_name = template_metadata["base_name"]
        for sequence, temporary in enumerate(sorted(template_outputs.glob("*.jpg")), start=1):
            temporary.replace(template_finals / f"{base_name}_{sequence:03d}.jpg")
        template_archive = root / f"{base_name}.zip"
        with zipfile.ZipFile(template_archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
            for final_image in sorted(template_finals.glob("*.jpg")):
                bundle.write(final_image, arcname=final_image.name)
        update_job(job_id, status="completed", output_path=str(template_archive))
        shutil.rmtree(cutouts, ignore_errors=True)
        shutil.rmtree(template_outputs, ignore_errors=True)
    except Exception as exc:
        update_job(job_id, status="failed", error=str(exc)[:2000])


@celery_app.task(name="app.workers.process_job")
def process_job_task(job_id: str) -> None:
    process_job(job_id)
