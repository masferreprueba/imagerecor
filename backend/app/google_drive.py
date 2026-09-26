import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Settings

# Limit the OAuth grant to files created or explicitly opened by this app.
# The uploader only creates a ZIP-named folder and new PNG files; it does not
# need permission to read or manage the rest of the user's Drive.
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"


def folder_name_from_zip(filename: str) -> str:
    client_name = filename.replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"\.zip$", "", client_name, flags=re.IGNORECASE).strip()
    return name[:200] or "Imagenes procesadas"


def _service_account_info(raw_value: str) -> dict:
    value = raw_value.strip()
    if not value:
        raise ValueError("Falta GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON.")
    if value.startswith("{"):
        return json.loads(value)
    return json.loads(Path(value).read_text(encoding="utf-8"))


def _drive_credentials(settings: "Settings"):
    from google.oauth2 import service_account
    from google.oauth2.credentials import Credentials

    if settings.google_drive_oauth_refresh_token:
        if not settings.google_drive_oauth_client_id or not settings.google_drive_oauth_client_secret:
            raise ValueError("Faltan las credenciales OAuth de Google Drive.")
        return Credentials(
            token=None,
            refresh_token=settings.google_drive_oauth_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_drive_oauth_client_id,
            client_secret=settings.google_drive_oauth_client_secret,
            scopes=[DRIVE_SCOPE],
        )
    return service_account.Credentials.from_service_account_info(
        _service_account_info(settings.google_drive_service_account_json),
        scopes=[DRIVE_SCOPE],
    )


def get_storage_quota(settings: "Settings") -> dict[str, int | float | None]:
    from googleapiclient.discovery import build

    if not settings.google_drive_enabled:
        raise RuntimeError("Google Drive todavía no está habilitado en el servidor.")
    drive = build("drive", "v3", credentials=_drive_credentials(settings), cache_discovery=False)
    quota = drive.about().get(fields="storageQuota").execute().get("storageQuota", {})
    used = int(quota.get("usage", 0))
    limit = int(quota["limit"]) if quota.get("limit") else None
    available = max(limit - used, 0) if limit is not None else None
    percent = min((used / limit) * 100, 100) if limit else None
    return {"used_bytes": used, "limit_bytes": limit, "available_bytes": available, "used_percent": percent}


def upload_png_folder(
    settings: "Settings",
    zip_filename: str,
    png_directory: Path,
) -> str:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    if not settings.google_drive_enabled:
        raise RuntimeError("Google Drive todavía no está habilitado en el servidor.")
    if not settings.google_drive_folder_id:
        raise RuntimeError("Falta GOOGLE_DRIVE_FOLDER_ID.")
    credentials = _drive_credentials(settings)
    drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
    folder = drive.files().create(
        body={
            "name": folder_name_from_zip(zip_filename),
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [settings.google_drive_folder_id],
        },
        fields="id,webViewLink",
        supportsAllDrives=True,
    ).execute()
    folder_id = folder["id"]
    for image in sorted(png_directory.glob("*.png")):
        drive.files().create(
            body={"name": image.name, "parents": [folder_id]},
            media_body=MediaFileUpload(str(image), mimetype="image/png", resumable=True),
            fields="id",
            supportsAllDrives=True,
        ).execute()
    return folder.get("webViewLink") or f"https://drive.google.com/drive/folders/{folder_id}"
