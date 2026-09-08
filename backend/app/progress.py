def calculate_progress(status: str, total: int, processed: int, failed: int) -> float:
    """Return a monotonic, stage-aware percentage for the user interface."""
    if status == "completed":
        return 100.0
    if status == "queued":
        return 15.0
    if status == "extracting":
        return 20.0
    if status == "packaging":
        return 95.0
    if status == "failed":
        return min(95.0, round(25.0 + ((processed + failed) / max(total, 1)) * 65.0, 1))
    if status == "processing":
        return min(90.0, round(25.0 + ((processed + failed) / max(total, 1)) * 65.0, 1))
    return 0.0
