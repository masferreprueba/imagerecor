from app.progress import calculate_progress


def test_progress_uses_clear_processing_stages():
    assert calculate_progress("queued", 6, 0, 0) == 15.0
    assert calculate_progress("extracting", 6, 0, 0) == 20.0
    assert calculate_progress("processing", 6, 0, 0) == 25.0
    assert calculate_progress("processing", 6, 3, 0) == 57.5
    assert calculate_progress("packaging", 6, 6, 0) == 95.0
    assert calculate_progress("completed", 6, 6, 0) == 100.0


def test_processing_progress_counts_failed_images_without_exceeding_packaging():
    assert calculate_progress("processing", 4, 2, 1) == 73.8
    assert calculate_progress("processing", 1, 2, 0) == 90.0
