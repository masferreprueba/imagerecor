import json
from pathlib import Path


DEFAULT_JOB_METADATA = {
    "output_mode": "standard",
    "drive_status": None,
    "drive_folder_url": None,
    "drive_error": None,
}


def read_job_metadata(job_root: Path) -> dict:
    path = job_root / "metadata.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        data = {}
    return {**DEFAULT_JOB_METADATA, **data}


def update_job_metadata(job_root: Path, **values) -> dict:
    metadata = read_job_metadata(job_root)
    metadata.update(values)
    job_root.mkdir(parents=True, exist_ok=True)
    path = job_root / "metadata.json"
    temporary = job_root / "metadata.json.tmp"
    temporary.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)
    return metadata
