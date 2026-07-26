from __future__ import annotations

from pathlib import Path
from datetime import datetime

from bisect import bisect_right

from PySide6.QtCore import QObject, QRunnable, QSettings, QThreadPool, Signal, Slot
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QTextCursor, QTextFormat
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from ..i18n import tr
from ..lyrics import (
    LyricsDocument,
    LyricsRequest,
    LyricsResolution,
    LyricsResolver,
    build_embedding_plan,
    embed_lyrics,
    read_duration_seconds,
    save_sidecar,
)
from ..models.song import Song


class LyricsWorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class LyricsWorker(QRunnable):
    def __init__(self, function, *args, **kwargs) -> None:
        super().__init__()
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.signals = LyricsWorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.function(*self.args, **self.kwargs)
        except Exception as error:
            self.signals.failed.emit(str(error))
            return
        self.signals.finished.emit(result)


class LyricsDialog(QDialog):
    def __init__(
        self,
        song: Song,
        parent=None,
        *,
        resolver: LyricsResolver | None = None,
        player_engine=None,
        language: str = "automatic",
    ) -> None:
        super().__init__(parent)
        self.language = language
        self.song = song
        self.resolver = resolver or LyricsResolver()
        self.player_engine = player_engine
        self.settings = QSettings("MusicTagStudio", "MusicTagStudio")
        self._karaoke_line = -1
        self.thread_pool = QThreadPool.globalInstance()
        self._workers: set[LyricsWorker] = set()
        self._closing = False
        self.documents: list[LyricsDocument] = []
        self.request = LyricsRequest(
            audio_path=song.path,
            title=song.title,
            artist=song.artist,
            album=song.album,
            duration=read_duration_seconds(song.path),
        )
        self._lrclib_ready = bool(
            self.request.title.strip()
            and self.request.artist.strip()
            and self.request.album.strip()
            and self.request.duration > 0
        )

        unknown_title = tr("unknown_title", language)
        self.setWindowTitle(
            tr("lyrics_dialog_title", language, title=song.title or unknown_title)
        )
        self.resize(780, 680)
        layout = QVBoxLayout(self)

        title = QLabel(song.title or unknown_title)
        title.setObjectName("lyricsTitle")
        title.setStyleSheet("font-size: 19px; font-weight: 600;")
        layout.addWidget(title)
        layout.addWidget(QLabel(tr(
            "song_meta_line",
            language,
            artist=song.artist or tr("unknown_artist", language),
            album=song.album or tr("no_album", language),
        )))

        source_row = QHBoxLayout()
        source_row.addWidget(QLabel(tr("source_colon", language)))
        self.source_combo = QComboBox()
        self.source_combo.setAccessibleName(tr("lyrics_source_acc", language))
        self.source_combo.currentIndexChanged.connect(self._source_changed)
        source_row.addWidget(self.source_combo, stretch=1)
        self.timestamps_checkbox = QCheckBox(tr("show_timestamps", language))
        self.timestamps_checkbox.setToolTip(
            tr("show_timestamps_tip", language)
        )
        self.timestamps_checkbox.toggled.connect(self._refresh_display)
        self.timestamps_checkbox.setEnabled(False)
        source_row.addWidget(self.timestamps_checkbox)
        source_row.addWidget(QLabel(tr("view", language)))
        self.view_combo = QComboBox()
        self.view_combo.addItems([tr("view_text", language), tr("view_karaoke", language)])
        self.view_combo.setAccessibleName(tr("lyrics_view_acc", language))
        self.view_combo.setToolTip(
            tr("karaoke_tip", language)
        )
        self.view_combo.currentIndexChanged.connect(self._view_changed)
        source_row.addWidget(self.view_combo)
        layout.addLayout(source_row)

        self.source_details = QLabel()
        self.source_details.setStyleSheet("color: palette(mid);")
        layout.addWidget(self.source_details)

        self.warning_label = QLabel()
        self.warning_label.setWordWrap(True)
        self.warning_label.setObjectName("lyricsWarning")
        self.warning_label.setStyleSheet(
            "padding: 9px; border: 1px solid #d69e2e; "
            "border-radius: 7px; background: rgba(214, 158, 46, 35);"
        )
        self.warning_label.hide()
        layout.addWidget(self.warning_label)

        self.lyrics_text = QPlainTextEdit()
        self.lyrics_text.setObjectName("lyricsDisplay")
        self.lyrics_text.setReadOnly(True)
        self.lyrics_text.setAccessibleName(tr("lyrics_display_acc", language))
        self.lyrics_text.setPlaceholderText(tr("no_local_lyrics", language))
        layout.addWidget(self.lyrics_text, stretch=1)

        actions = QHBoxLayout()
        self.cached_button = QPushButton(tr("check_lrclib", language))
        self.cached_button.setToolTip(
            tr("check_lrclib_tip", language)
        )
        self.cached_button.clicked.connect(lambda: self._load_online(live=False))
        actions.addWidget(self.cached_button)
        self.live_button = QPushButton(tr("lrclib_live_search", language))
        self.live_button.setToolTip(
            tr("lrclib_live_tip", language)
        )
        self.live_button.clicked.connect(lambda: self._load_online(live=True))
        actions.addWidget(self.live_button)
        actions.addStretch()
        self.save_button = QPushButton(tr("save_as_lrc", language))
        self.save_button.clicked.connect(self._save_selected)
        self.save_button.setEnabled(False)
        actions.addWidget(self.save_button)
        self.embed_button = QPushButton(tr("embed_in_audio", language))
        self.embed_button.clicked.connect(self._preview_embedding)
        self.embed_button.setEnabled(False)
        actions.addWidget(self.embed_button)
        layout.addLayout(actions)

        self.status_label = QLabel()
        self.status_label.setObjectName("lyricsStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        if not self._lrclib_ready:
            self._set_status(
                tr("lrclib_incomplete", language),
                "incomplete",
            )
            self.cached_button.setEnabled(False)
            self.live_button.setEnabled(False)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._add_shortcuts()

        if self.player_engine is not None:
            self.player_engine.position_changed.connect(
                self._update_karaoke
            )
            self.player_engine.song_changed.connect(
                self._player_song_changed
            )

        self._apply_resolution(self.resolver.local(self.request))
        if not self.documents and self._lrclib_ready:
            self._set_status(
                tr("no_local_lyrics_hint", self.language),
                "info",
            )

    def _apply_resolution(self, resolution: LyricsResolution) -> None:
        self.documents = list(resolution.candidates)
        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        for document in self.documents:
            kind = (
                tr("kind_synced", self.language)
                if document.is_synced
                else tr("kind_unsynced", self.language)
            )
            if document.instrumental:
                kind = tr("kind_instrumental", self.language)
            self.source_combo.addItem(
                f"{_source_display_name(document, self.language)} · {kind}"
            )
        self.source_combo.blockSignals(False)
        if resolution.selected in self.documents:
            self.source_combo.setCurrentIndex(
                self.documents.index(resolution.selected)
            )
        elif self.documents:
            self.source_combo.setCurrentIndex(0)
        self._show_document(self.current_document(), resolution.warning)

    def current_document(self) -> LyricsDocument | None:
        index = self.source_combo.currentIndex()
        if 0 <= index < len(self.documents):
            return self.documents[index]
        return None

    def _source_changed(self, _index: int) -> None:
        document = self.current_document()
        from ..lyrics.resolver import live_version_warning

        self._show_document(
            document,
            live_version_warning(self.request, document),
        )

    def _show_document(
        self,
        document: LyricsDocument | None,
        warning: str = "",
    ) -> None:
        if document is None:
            self.lyrics_text.clear()
            self.source_details.setText(tr("no_local_source", self.language))
            self.timestamps_checkbox.setChecked(False)
            self.timestamps_checkbox.setEnabled(False)
            self.save_button.setEnabled(False)
            self.embed_button.setEnabled(False)
            self.view_combo.setCurrentIndex(0)
            self.view_combo.setEnabled(False)
        else:
            if not document.is_synced and self.timestamps_checkbox.isChecked():
                self.timestamps_checkbox.blockSignals(True)
                self.timestamps_checkbox.setChecked(False)
                self.timestamps_checkbox.blockSignals(False)
            self.timestamps_checkbox.setEnabled(document.is_synced)
            self.view_combo.setEnabled(
                document.is_synced and self.player_engine is not None
            )
            wanted_karaoke = (
                self.settings.value("lyrics/view_mode", "text") == "karaoke"
                and self.view_combo.isEnabled()
            )
            self.view_combo.blockSignals(True)
            self.view_combo.setCurrentIndex(1 if wanted_karaoke else 0)
            self.view_combo.blockSignals(False)
            self._render_document(document)
            details = [_source_display_name(document, self.language)]
            if document.provider_id:
                details.append(tr("source_id", self.language, id=document.provider_id))
            if document.fetched_at:
                details.append(tr(
                    "fetched_at",
                    self.language,
                    when=_format_fetched_at(document.fetched_at),
                ))
            self.source_details.setText(" · ".join(details))
            self.save_button.setEnabled(not document.is_empty)
            plan = build_embedding_plan(self.song.path, document)
            self.embed_button.setEnabled(
                not document.is_empty
                and plan.supported
                and Path(self.song.path).is_file()
            )
            self.embed_button.setToolTip(
                tr("target_format", self.language, format=plan.format_name)
                if plan.supported
                else plan.warning
            )
        self.warning_label.setText(warning)
        self.warning_label.setVisible(bool(warning))

    def _render_document(self, document: LyricsDocument) -> None:
        karaoke = self.view_combo.currentIndex() == 1 and document.is_synced
        self.timestamps_checkbox.setEnabled(document.is_synced and not karaoke)
        if karaoke:
            self.lyrics_text.setPlainText(
                "\n".join(line.text for line in document.synced_lines)
            )
            self._karaoke_line = -1
            position = (
                self.player_engine.media_player.position()
                if self.player_engine is not None
                else 0
            )
            self._update_karaoke(position)
            return
        self.lyrics_text.setExtraSelections([])
        self._karaoke_line = -1
        self.lyrics_text.setPlainText(
            _document_display_text(
                document,
                show_timestamps=(
                    self.timestamps_checkbox.isChecked()
                    and document.is_synced
                ),
            )
        )

    def _view_changed(self, index: int) -> None:
        document = self.current_document()
        if document is None:
            return
        karaoke = index == 1 and document.is_synced
        self.settings.setValue(
            "lyrics/view_mode", "karaoke" if karaoke else "text"
        )
        self._render_document(document)

    def _player_song_changed(self, _song: Song | None) -> None:
        if self.view_combo.currentIndex() == 1:
            position = (
                self.player_engine.media_player.position()
                if self.player_engine is not None
                else 0
            )
            self._update_karaoke(position)

    def _player_matches_song(self) -> bool:
        if self.player_engine is None or self.player_engine.current_song is None:
            return False
        return (
            Path(self.player_engine.current_song.path)
            == Path(self.song.path)
        )

    def _update_karaoke(self, position_ms: int) -> None:
        document = self.current_document()
        if (
            document is None
            or not document.synced_lines
            or self.view_combo.currentIndex() != 1
        ):
            return
        if not self._player_matches_song():
            self.lyrics_text.setExtraSelections([])
            self._karaoke_line = -1
            return
        times = [line.time_ms for line in document.synced_lines]
        line_index = bisect_right(times, max(0, int(position_ms))) - 1
        if line_index < 0 or line_index == self._karaoke_line:
            return
        cursor = self.lyrics_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        cursor.movePosition(
            QTextCursor.MoveOperation.Down,
            QTextCursor.MoveMode.MoveAnchor,
            line_index,
        )
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        selection = QTextEdit.ExtraSelection()
        selection.cursor = cursor
        selection.format.setBackground(
            self.palette().highlight().color()
        )
        selection.format.setForeground(
            self.palette().highlightedText().color()
        )
        selection.format.setProperty(
            QTextFormat.Property.FullWidthSelection,
            True,
        )
        self.lyrics_text.setExtraSelections([selection])
        self.lyrics_text.setTextCursor(cursor)
        self.lyrics_text.centerCursor()
        self._karaoke_line = line_index

    def _load_online(self, *, live: bool) -> None:
        if not self._lrclib_ready:
            return
        self._set_loading(True)
        self._set_status(
            tr("lrclib_live_running", self.language)
            if live
            else tr("lrclib_cache_checking", self.language),
            "loading",
        )
        worker = LyricsWorker(self.resolver.online, self.request, live=live)
        self._workers.add(worker)
        worker.signals.finished.connect(self._online_loaded)
        worker.signals.failed.connect(self._online_failed)
        worker.signals.finished.connect(lambda _result, item=worker: self._release_worker(item))
        worker.signals.failed.connect(lambda _error, item=worker: self._release_worker(item))
        self.thread_pool.start(worker)

    def _online_loaded(self, resolution: LyricsResolution) -> None:
        if self._closing:
            return
        self._set_loading(False)
        self._set_status(
            tr("lyrics_loaded_cached", self.language),
            "success",
        )
        self._apply_resolution(resolution)

    def _online_failed(self, message: str) -> None:
        if self._closing:
            return
        self._set_loading(False)
        lowered = message.casefold()
        if any(
            phrase in lowered
            for phrase in (
                "nicht gefunden",
                "keine lyrics",
                "keinen liedtext",
            )
        ):
            text = tr("lrclib_no_match", self.language)
            kind = "not_found"
        elif "nicht erreichbar" in lowered or "timeout" in lowered:
            text = tr("lrclib_offline", self.language)
            kind = "offline"
        else:
            text = message
            kind = "error"
        self._set_status(text, kind)

    def _release_worker(self, worker: LyricsWorker) -> None:
        self._workers.discard(worker)

    def _set_loading(self, loading: bool) -> None:
        enabled = self._lrclib_ready and not loading
        self.cached_button.setEnabled(enabled)
        self.live_button.setEnabled(enabled)

    def _save_selected(self) -> None:
        document = self.current_document()
        if document is None:
            return
        try:
            destination = save_sidecar(self.song.path, document)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, tr("save_lyrics_title", self.language), str(error))
            return
        self._set_status(
            tr("lrc_saved", self.language, path=destination), "success"
        )
        self._apply_resolution(self.resolver.local(self.request))

    def _preview_embedding(self) -> None:
        document = self.current_document()
        if document is None:
            return
        if not Path(self.song.path).is_file():
            self._set_status(
                tr("audio_unreachable_edit", self.language),
                "offline",
            )
            return
        plan = build_embedding_plan(self.song.path, document)
        if not plan.supported:
            QMessageBox.warning(
                self, tr("embed_lyrics_title", self.language), plan.warning
            )
            return
        preview = LyricsEmbedPreviewDialog(plan, document, self, language=self.language)
        if preview.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            embed_lyrics(self.song.path, document, confirmed=True)
        except Exception as error:
            QMessageBox.critical(
                self, tr("embed_lyrics_title", self.language), str(error)
            )
            return
        self._set_status(
            tr("lyrics_embedded", self.language, format=plan.format_name),
            "success",
        )
        self._apply_resolution(self.resolver.local(self.request))

    def closeEvent(self, event: QCloseEvent) -> None:
        self._closing = True
        if self.player_engine is not None:
            try:
                self.player_engine.position_changed.disconnect(
                    self._update_karaoke
                )
                self.player_engine.song_changed.disconnect(
                    self._player_song_changed
                )
            except (RuntimeError, TypeError):
                pass
        super().closeEvent(event)

    def _refresh_display(self, _checked: bool = False) -> None:
        document = self.current_document()
        if document is not None:
            self._show_document(document, self.warning_label.text())

    def _set_status(self, text: str, kind: str = "info") -> None:
        self.status_label.setText(text)
        self.status_label.setProperty("statusKind", kind)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _add_shortcuts(self) -> None:
        shortcuts = (
            ("Ctrl+L", lambda: self._load_online(live=True)),
            ("Ctrl+S", self._save_selected),
            ("Ctrl+E", self._preview_embedding),
        )
        for sequence, callback in shortcuts:
            action = QAction(self)
            action.setShortcut(QKeySequence(sequence))
            action.triggered.connect(callback)
            self.addAction(action)


class LyricsEmbedPreviewDialog(QDialog):
    def __init__(
        self,
        plan,
        document: LyricsDocument,
        parent=None,
        *,
        language: str = "automatic",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("embed_confirm_title", language))
        self.resize(900, 620)
        layout = QVBoxLayout(self)
        summary = QLabel(
            tr(
                "embed_summary",
                language,
                format=plan.format_name,
                count=len(plan.existing),
            )
        )
        summary.setWordWrap(True)
        layout.addWidget(summary)
        if plan.warning:
            warning = QLabel(plan.warning)
            warning.setWordWrap(True)
            warning.setStyleSheet(
                "padding: 9px; border: 1px solid #d69e2e; border-radius: 7px;"
            )
            layout.addWidget(warning)

        comparison = QHBoxLayout()
        before_layout = QVBoxLayout()
        before_layout.addWidget(QLabel(tr("currently_embedded", language)))
        before = QPlainTextEdit()
        before.setReadOnly(True)
        before.setPlainText(
            "\n\n".join(
                f"--- {item.source} ---\n{item.display_text()}"
                for item in plan.existing
            )
            or tr("no_embedded_lyrics", language)
        )
        before_layout.addWidget(before)
        comparison.addLayout(before_layout, stretch=1)

        after_layout = QVBoxLayout()
        after_layout.addWidget(QLabel(tr("will_be_embedded", language)))
        after = QPlainTextEdit()
        after.setReadOnly(True)
        after.setPlainText(document.display_text())
        after_layout.addWidget(after)
        comparison.addLayout(after_layout, stretch=1)
        layout.addLayout(comparison, stretch=1)

        note = QLabel(
            tr("embed_note", language)
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Save
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(
            tr("embed_confirmed_btn", language)
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


def _source_display_name(document: LyricsDocument, language: str = "automatic") -> str:
    source = document.source
    if source == "LRC-Datei":
        return tr("lrc_local_file", language)
    if source.startswith("Eingebettete Lyrics"):
        return "🎵 " + source
    if source == "LRCLIB":
        return tr("lrclib_cached_source", language)
    return source or tr("unknown_source", language)


def _format_fetched_at(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone().strftime("%d.%m.%Y, %H:%M")
    except (TypeError, ValueError):
        return value


def _document_display_text(
    document: LyricsDocument,
    *,
    show_timestamps: bool,
) -> str:
    if not show_timestamps or not document.synced_lines:
        return document.display_text()
    lines = []
    for line in document.synced_lines:
        minutes, remainder = divmod(max(0, line.time_ms), 60_000)
        seconds, milliseconds = divmod(remainder, 1_000)
        lines.append(
            f"[{minutes:02d}:{seconds:02d}.{milliseconds // 10:02d}] {line.text}"
        )
    return "\n".join(lines)
