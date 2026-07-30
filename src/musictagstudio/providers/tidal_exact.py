"""Exakte TIDAL-Qualität über die inoffizielle App-API (tidalapi).

Bewusst getrennt vom offiziellen Katalog-Abgleich (``providers/tidal.py``,
``search.read``). Diese Anbindung nutzt die **interne** TIDAL-API und erfordert
einen **eigenen TIDAL-Login** des Nutzers (Hi-Fi-Abo). Sie ist optional,
undokumentiert und liegt in einem ToS-Graubereich – daher opt-in.

Nur so liefert TIDAL die tatsächliche Bit-Tiefe/Abtastrate einer
Veröffentlichung; die offizielle API kennt nur die Qualitäts*stufe*.

Die tidalapi-Aufrufe sind über schlanke Wrapper gekapselt, damit die
Auswertungslogik ohne echtes Konto testbar bleibt.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ExactQuality:
    bit_depth: int = 0
    sample_rate: int = 0
    audio_quality: str = ""  # TIDAL-Stufe, z. B. "HI_RES_LOSSLESS"
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and bool(self.sample_rate or self.bit_depth)

    @property
    def sample_rate_text(self) -> str:
        return f"{self.sample_rate / 1000:.1f} kHz" if self.sample_rate else ""

    @property
    def bit_depth_text(self) -> str:
        return f"{self.bit_depth} Bit" if self.bit_depth else ""

    def summary(self) -> str:
        """z. B. 'FLAC · 24 Bit · 48.0 kHz' bzw. Fehlermeldung."""
        if self.error:
            return self.error
        parts: list[str] = []
        tier = _tier_label(self.audio_quality)
        if tier:
            parts.append(tier)
        if self.bit_depth_text:
            parts.append(self.bit_depth_text)
        if self.sample_rate_text:
            parts.append(self.sample_rate_text)
        return " · ".join(parts) if parts else "Keine Angabe"


_TIER_LABELS = {
    "HI_RES_LOSSLESS": "Hi-Res Lossless",
    "HIRES_LOSSLESS": "Hi-Res Lossless",
    "LOSSLESS": "Lossless",
    "HIGH": "AAC 320 kbit/s",
    "LOW": "AAC 96 kbit/s",
    "DOLBY_ATMOS": "Dolby Atmos",
}


def _tier_label(audio_quality: str) -> str:
    return _TIER_LABELS.get(str(audio_quality or "").strip().upper(), "")


def _as_int(value: object) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def extract_stream_quality(stream: object, *, fallback_quality: str = "") -> ExactQuality:
    """Liest Bit-Tiefe/Abtastrate aus einem tidalapi-Stream-Objekt (defensiv)."""
    if stream is None:
        return ExactQuality(
            audio_quality=str(fallback_quality or ""),
            error="Kein Stream verfügbar",
        )
    return ExactQuality(
        bit_depth=_as_int(getattr(stream, "bit_depth", 0)),
        sample_rate=_as_int(getattr(stream, "sample_rate", 0)),
        audio_quality=str(
            getattr(stream, "audio_quality", "") or fallback_quality or ""
        ),
    )


def album_exact_quality(session: object, album_id: str) -> ExactQuality:
    """Ermittelt die exakte Qualität einer TIDAL-Veröffentlichung.

    ``session`` ist eine eingeloggte tidalapi-Session (oder ein kompatibles
    Objekt). Es wird ein repräsentativer Titel des Albums herangezogen und
    dessen tatsächlicher Stream ausgewertet.
    """
    try:
        album = session.album(album_id)
        tracks = list(album.tracks())
    except Exception:
        return ExactQuality(error="Album konnte nicht geladen werden")
    if not tracks:
        return ExactQuality(error="Keine Titel gefunden")

    track = tracks[0]
    fallback = str(getattr(track, "audio_quality", "") or "")
    try:
        stream = track.get_stream()
    except Exception:
        # Kein Stream (z. B. kein Abo) -> wenigstens die Stufe des Titels.
        return ExactQuality(
            audio_quality=fallback,
            error="Stream nicht abrufbar (Abo/Berechtigung?)",
        )
    return extract_stream_quality(stream, fallback_quality=fallback)


# --- tidalapi-Session (inoffizielle App-API; eigener Login nötig) ------------
#
# Die Wrapper importieren tidalapi lazy, damit dieses Modul (und seine testbare
# Auswertungslogik) auch ohne installiertes tidalapi importierbar bleibt.


def is_available() -> bool:
    try:
        import tidalapi  # noqa: F401
    except Exception:
        return False
    return True


def new_session():
    """Neue tidalapi-Session, die die höchste Qualität anfordert."""
    import tidalapi

    session = tidalapi.Session()
    try:
        session.audio_quality = tidalapi.Quality.hi_res_lossless
    except Exception:
        pass
    return session


def start_device_login(session):
    """Startet den OAuth-Device-Flow.

    Gibt ``(login, future)`` zurück: ``login.verification_uri_complete`` und
    ``login.user_code`` für die Anzeige; ``future`` ist fertig, sobald der
    Nutzer im Browser autorisiert hat.
    """
    return session.login_oauth()


def session_credentials(session) -> dict:
    """Serialisierbare Zugangsdaten der Session (zum lokalen Speichern)."""
    expiry = getattr(session, "expiry_time", None)
    return {
        "token_type": str(getattr(session, "token_type", "") or ""),
        "access_token": str(getattr(session, "access_token", "") or ""),
        "refresh_token": str(getattr(session, "refresh_token", "") or ""),
        "expiry_time": expiry.isoformat() if isinstance(expiry, datetime) else "",
    }


def restore_session(creds: dict):
    """Stellt eine eingeloggte Session aus gespeicherten Daten her; sonst None."""
    if not creds or not creds.get("access_token"):
        return None
    expiry = None
    raw_expiry = creds.get("expiry_time")
    if raw_expiry:
        try:
            expiry = datetime.fromisoformat(str(raw_expiry))
        except ValueError:
            expiry = None
    try:
        session = new_session()
        ok = session.load_oauth_session(
            creds.get("token_type") or "Bearer",
            creds["access_token"],
            creds.get("refresh_token") or None,
            expiry,
        )
    except Exception:
        return None
    if not ok:
        return None
    try:
        return session if session.check_login() else None
    except Exception:
        return None

# --- Lokale Speicherung der Session (opt-in) --------------------------------

_SECRET_NAME = "tidal_exact_session"


def save_credentials(creds: dict) -> None:
    """Speichert die Session-Zugangsdaten lokal (secret_store)."""
    import json

    from .. import secret_store

    secret_store.set_secret(_SECRET_NAME, json.dumps(creds))


def load_credentials() -> dict | None:
    import json

    from .. import secret_store

    raw = secret_store.get_secret(_SECRET_NAME)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def is_connected() -> bool:
    creds = load_credentials()
    return bool(creds and creds.get("access_token"))


def disconnect() -> None:
    from .. import secret_store

    secret_store.set_secret(_SECRET_NAME, "")


def stored_session():
    """Stellt die gespeicherte Session wieder her (oder None)."""
    return restore_session(load_credentials() or {})
