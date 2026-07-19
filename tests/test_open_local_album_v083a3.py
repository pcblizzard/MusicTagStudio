import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from musictagstudio.media_library.service import ReleaseGroup
from musictagstudio.ui.media_library_widget import MediaLibraryWidget


def test_local_album_button_emits_album_folder(tmp_path):
    app = QApplication.instance() or QApplication([])
    widget = MediaLibraryWidget()
    widget._run = lambda *args, **kwargs: None
    album_path = str(tmp_path / "Clueso" / "Deja Vu 1-2")
    key = "dejavu12"
    widget.local_albums = {key: album_path}
    widget.local_album_status = {key: "Lokal verfügbar"}
    opened = []
    widget.open_local_album.connect(opened.append)

    widget._load_group(
        ReleaseGroup(
            release_group_id="release-group-id",
            title="Deja Vu 1/2",
        )
    )
    widget.open_local_button.click()

    assert widget.open_local_button.property("local_path") == album_path
    assert opened == [album_path]
    widget.close()
    app.processEvents()
