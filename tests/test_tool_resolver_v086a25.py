from musictagstudio.audio_analysis import ffmpeg_tools
from musictagstudio.providers import fingerprint


def test_find_ffprobe_prefers_bundled(tmp_path, monkeypatch):
    bundled = tmp_path / "tools" / "ffmpeg"
    bundled.mkdir(parents=True)
    name = ffmpeg_tools.executable_name("ffprobe")
    (bundled / name).write_bytes(b"x")

    monkeypatch.setattr(ffmpeg_tools, "application_root", lambda: tmp_path)
    monkeypatch.setattr(
        ffmpeg_tools.shutil, "which", lambda _n: "C:/system/ffprobe.exe"
    )

    resolved = ffmpeg_tools.find_ffprobe()
    assert resolved.endswith(name)
    assert str(tmp_path) in resolved  # mitgeliefert, nicht PATH


def test_find_ffprobe_falls_back_to_path(tmp_path, monkeypatch):
    monkeypatch.setattr(ffmpeg_tools, "application_root", lambda: tmp_path)
    monkeypatch.setattr(
        ffmpeg_tools.shutil, "which", lambda _n: "C:/system/ffprobe.exe"
    )
    assert ffmpeg_tools.find_ffprobe() == "C:/system/ffprobe.exe"


def test_find_ffprobe_returns_empty_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(ffmpeg_tools, "application_root", lambda: tmp_path)
    monkeypatch.setattr(ffmpeg_tools.shutil, "which", lambda _n: None)
    assert ffmpeg_tools.find_ffprobe() == ""


def test_find_fpcalc_prefers_tools_dir(tmp_path, monkeypatch):
    tools = tmp_path / "fpcalc"
    tools.mkdir(parents=True)
    binary = tools / "fpcalc.exe"
    binary.write_bytes(b"x")

    monkeypatch.setattr(fingerprint, "_tools_dir", lambda: tools)
    monkeypatch.setattr(
        fingerprint.shutil, "which", lambda _n: "C:/system/fpcalc.exe"
    )

    assert fingerprint.find_fpcalc("") == str(binary)
