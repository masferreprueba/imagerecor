from app.job_metadata import read_job_metadata, update_job_metadata


def test_job_metadata_defaults_to_standard_mode(tmp_path):
    metadata = read_job_metadata(tmp_path)

    assert metadata["output_mode"] == "standard"
    assert metadata["drive_status"] is None


def test_job_metadata_preserves_existing_values(tmp_path):
    update_job_metadata(tmp_path, output_mode="png_4000", drive_status="pending")
    update_job_metadata(tmp_path, drive_status="completed", drive_folder_url="https://drive.example/folder")

    metadata = read_job_metadata(tmp_path)

    assert metadata["output_mode"] == "png_4000"
    assert metadata["drive_status"] == "completed"
    assert metadata["drive_folder_url"] == "https://drive.example/folder"
