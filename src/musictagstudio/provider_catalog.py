from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ProviderStatus = Literal[
    "supported",
    "setup_required",
    "unsupported",
]


@dataclass(frozen=True)
class ProviderDefinition:
    provider_id: str
    name: str
    status: ProviderStatus
    status_text: str
    tooltip: str

    @property
    def selectable(self) -> bool:
        return self.status in {
            "supported",
            "setup_required",
        }


PROVIDERS: tuple[ProviderDefinition, ...] = (
    ProviderDefinition(
        provider_id="apple_music",
        name="Apple Music",
        status="supported",
        status_text="Unterstützt",
        tooltip=(
            "In MusicTagStudio unterstützt.\n\n"
            "Nutzt die öffentliche Apple iTunes Search API. "
            "Für die Metadatensuche ist keine Anmeldung und keine "
            "Apple-Music-Mitgliedschaft erforderlich."
        ),
    ),
    ProviderDefinition(
        provider_id="musicbrainz",
        name="MusicBrainz",
        status="supported",
        status_text="Unterstützt",
        tooltip=(
            "In MusicTagStudio unterstützt.\n\n"
            "Nutzt die offizielle MusicBrainz Web API. "
            "MusicBrainz eignet sich besonders als freie Quelle für "
            "ISRC, Label, Komponisten und weitere Metadaten."
        ),
    ),
    ProviderDefinition(
        provider_id="tidal",
        name="TIDAL",
        status="unsupported",
        status_text="Aktuell nicht unterstützt",
        tooltip=(
            "In MusicTagStudio derzeit nicht implementiert.\n\n"
            "MusicTagStudio verwendet ausschließlich offiziell "
            "dokumentierte Programmierschnittstellen."
        ),
    ),
    ProviderDefinition(
        provider_id="qobuz",
        name="Qobuz",
        status="unsupported",
        status_text="Aktuell nicht unterstützt",
        tooltip=(
            "In MusicTagStudio derzeit nicht unterstützt.\n\n"
            "MusicTagStudio verwendet ausschließlich offiziell "
            "dokumentierte Programmierschnittstellen. Derzeit wird "
            "keine geeignete öffentliche Schnittstelle für diese "
            "Integration verwendet."
        ),
    ),
    ProviderDefinition(
        provider_id="deezer",
        name="Deezer",
        status="unsupported",
        status_text="Aktuell nicht unterstützt",
        tooltip=(
            "In MusicTagStudio derzeit nicht implementiert.\n\n"
            "MusicTagStudio verwendet ausschließlich offiziell "
            "dokumentierte Programmierschnittstellen."
        ),
    ),
    ProviderDefinition(
        provider_id="amazon_music",
        name="Amazon Music",
        status="unsupported",
        status_text="Aktuell nicht unterstützt",
        tooltip=(
            "In MusicTagStudio derzeit nicht unterstützt.\n\n"
            "Der offizielle Amazon-Music-Web-API-Zugang ist derzeit "
            "nicht allgemein verfügbar."
        ),
    ),
    ProviderDefinition(
        provider_id="spotify",
        name="Spotify",
        status="unsupported",
        status_text="Aktuell nicht unterstützt",
        tooltip=(
            "In MusicTagStudio derzeit nicht implementiert.\n\n"
            "Die offizielle Spotify Web API erfordert eine registrierte "
            "Entwickleranwendung und eine Autorisierung."
        ),
    ),
    ProviderDefinition(
        provider_id="youtube_music",
        name="YouTube Music",
        status="unsupported",
        status_text="Aktuell nicht unterstützt",
        tooltip=(
            "In MusicTagStudio derzeit nicht implementiert.\n\n"
            "Eine offizielle Integration würde die YouTube Data API "
            "und einen eigenen Google-API-Schlüssel verwenden."
        ),
    ),
)


PROVIDERS_BY_ID = {
    provider.provider_id: provider
    for provider in PROVIDERS
}


def supported_provider_ids() -> tuple[str, ...]:
    return tuple(
        provider.provider_id
        for provider in PROVIDERS
        if provider.status == "supported"
    )
