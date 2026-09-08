from datetime import datetime
from pydantic import BaseModel


class Preview(BaseModel):
    name: str
    original_url: str
    processed_url: str | None = None
    status: str


class JobResponse(BaseModel):
    id: str
    filename: str
    provider: str
    status: str
    total_images: int
    processed_images: int
    failed_images: int
    progress: float
    error: str | None
    download_url: str | None
    previews: list[Preview]
    created_at: datetime
