from musictagstudio.services import scanner


def test_scan_reports_failures(
    monkeypatch,
    tmp_path,
):
    good = tmp_path / "good.wv"
    bad = tmp_path / "bad.wv"
    good.write_bytes(b"good")
    bad.write_bytes(b"bad")

    def fake_read(path):
        if path.name == "bad.wv":
            raise ValueError("kaputt")

        from musictagstudio.models.song import Song

        return Song(
            title="Good",
            path=str(path),
        )

    monkeypatch.setattr(
        scanner,
        "read_metadata",
        fake_read,
    )

    result = scanner.scan_folder_detailed(
        tmp_path
    )

    assert result.detected_files == 2
    assert result.successful_files == 1
    assert len(result.failures) == 1
    assert "kaputt" in result.failures[0].error
