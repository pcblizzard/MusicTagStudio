# MusicTagStudio

**English** | [Deutsch](README.de.md)

MusicTagStudio is a safety-focused, preview-first metadata editor, music
catalogue and local audio player for Windows. It connects local audio files
with MusicBrainz, Discogs, Apple Music, Deezer, TheAudioDB, Cover Art Archive
and LRCLIB without silently overwriting metadata.

Current development version: **v0.8.6-alpha2.3**

## Features

### Tag editor

- Edit individual tracks or complete albums
- Compare Apple Music and MusicBrainz independently
- Match complete album track lists instead of relying on uncertain single hits
- Preview every field before accepting external metadata
- Undo/redo and backups for write operations
- Search, compare, save and embed cover artwork
- Generate BBCode album templates

### Media library

- Live artist suggestions from MusicBrainz and Deezer
- Artist, release and label search
- Discographies, editions and track lists
- MusicBrainz relationships such as members, groups, aliases and labels
- Discogs additions for releases, labels, formats, covers and artist images
- Local Discogs cache; live refresh only after an explicit action
- Breadcrumb navigation and local-availability indicators
- Open recognised local albums directly in the tag editor
- Start local albums from the media-library track list
- Localised artist biographies and album descriptions with visible sources
- Apple Music editorial album text for unambiguous matches
- Artist artwork from Apple Music with a Discogs fallback
- Discography, table, cover-list and cover-grid views
- Persistent view mode, cover size and splitter positions
- Cached streaming availability across views and application restarts

### Lyrics

- Read embedded lyrics and local LRC files
- Support synchronised and unsynchronised lyrics
- Search LRCLIB and cache results locally
- Save selected lyrics as an atomic UTF-8 LRC sidecar
- Preview changes before embedding lyrics into an audio file
- Require confirmation before replacing embedded lyrics
- Warn when a live, concert or unplugged version only has studio lyrics
- Switch between plain text, timestamped LRC and karaoke display
- Highlight and follow the active karaoke line during playback

### Player

- Play local tracks from the tag editor and media library
- Persistent player bar with cover, title, album and position
- Play/pause, previous, next, seeking, volume and mute controls
- Dedicated queue window with multi-selection and drag-and-drop sorting
- Play now, play next, remove and clear queue actions
- Append local albums without replacing the active queue
- Two shuffle modes: navigable history or a fresh random selection
- Repeat the current track or the complete queue
- Preserve volume, mute, shuffle and repeat settings
- Skip missing files while advancing through the queue
- Spacebar play/pause outside text inputs
- Global Windows media keys for play/pause, previous, next and stop
- Windows system media display with title, artist, album, cover and status
- Highlight the playing track in the tag editor and media library

### Audio analysis and library audit

- Codec, container, sample rate, bit depth, channels, bitrate and duration
- LUFS, Loudness Range, True Peak and ReplayGain through FFmpeg/ffprobe
- Album comparison, persistent analysis cache and conservative health score
- Checks for duplicate ISRCs, inconsistent album fields, track-number gaps,
  cover differences and missing ReplayGain values
- Confirmed writing of calculated ReplayGain tags

### Interface

- Light, dark or automatic appearance
- German or English editorial information based on app or system language
- Separate workspaces for dashboard, tagger, media library, audio analysis and
  library audit
- Persistent window layouts and compact navigation

## Data sources

| Source | Purpose |
| --- | --- |
| Local library | Audio files, tags, covers, lyrics and playback |
| MusicBrainz | Artists, releases, editions and relationships |
| Discogs | Discographies, editions, labels, formats, covers and artist images |
| Apple Music | Album matching, track lists, covers, availability and editorial text |
| Deezer | Additional live artist suggestions |
| TheAudioDB | Localised artist biographies and album descriptions |
| Cover Art Archive | Additional cover candidates |
| LRCLIB | Synchronised and unsynchronised lyrics |

Online sources are used only for the purposes listed above. TIDAL, Qobuz,
Spotify, Amazon Music and YouTube Music are not currently integrated as full
catalogue or streaming providers.

## Supported audio formats

- FLAC
- MP3
- Ogg Vorbis and Opus
- M4A, MP4 and M4B
- WavPack (`.wv`)
- Monkey's Audio (`.ape`)
- WMA and ASF

Some metadata and lyrics capabilities depend on the container format.
MusicTagStudio shows affected values and limitations before writing.

## Installation on Windows

Windows and Python 3.12 or newer are required. **Python 3.13** is currently
recommended because preview releases of newer Python versions may not yet be
supported by PySide6.

```powershell
git clone https://github.com/pcblizzard/MusicTagStudio.git
cd MusicTagStudio
py -3.13 -m pip install --upgrade pip
py -3.13 -m pip install -e .
py -3.13 -m musictagstudio.main
```

Audio analysis and ReplayGain require `ffmpeg` and `ffprobe` on `PATH`. Both
tools are included in the FFmpeg package:

```powershell
winget install --id Gyan.FFmpeg --exact
```

Restart the terminal and verify the installation:

```powershell
ffmpeg -version
ffprobe -version
```

All tagging, catalogue, lyrics and player features that do not require audio
analysis remain available without FFmpeg.

## Configuration

Configure music sources under **File → Settings…** after the first start.
MusicTagStudio stores local settings in `config.toml`.

Appearance, language, Apple Music country, cover output and audio-analysis
parallelism can also be configured there.

Discogs is optional. A personal API token can be entered in Settings. Without
it, MusicBrainz, local media, lyrics and the remaining features are still
available. Never commit personal tokens or local media paths.

Online responses are cached where appropriate. Explicit actions such as
**Refresh Discogs live** or **Search LRCLIB live** intentionally bypass local
catalogue state.

Streaming availability uses a provider-neutral seven-day cache. Editorial
information has a separate, longer-lived cache.

## Safety

- External metadata is presented as a proposal first.
- Quality values are not guessed.
- Metadata, lyrics and ReplayGain are written only after an explicit action.
- Replacing embedded lyrics requires confirmation.
- Critical writes use backups or recovery on failure.

Keep a separate, verified backup of every important music library.

## Development and tests

```powershell
py -3.13 -m pip install -e ".[dev]"
py -3.13 -m pytest
py -3.13 scripts/release_check.py
```

The release check compiles the source tree, runs the complete test suite and
removes generated Python caches.

Important packages under `src/musictagstudio/`:

- `ui/` – Qt interface
- `services/` – tagging, scanning and application logic
- `providers/` – external metadata and music services
- `media_library/` – MusicBrainz/Discogs catalogue
- `media_library/streaming/` – streaming matching and provider-neutral cache
- `player/` – player engine, playback history and queue
- `lyrics/` – lyrics model, LRCLIB, LRC, cache and embedding
- `audio_analysis/` – technical audio analysis
- `library_audit/` – library checks
- `models/` and `core/` – shared data models and rules

See the [architecture documentation](docs/ARCHITECTURE.md), the
[coding guidelines](docs/CODING_GUIDELINES.md), the
[changelog](docs/CHANGELOG.md) and the [roadmap](docs/ROADMAP.md).

## Version overview

### v0.8.6-alpha2.3

- Dedicated queue window with drag-and-drop and multi-selection
- Append local albums to an existing queue
- Global media keys and Windows system media display
- Karaoke display for synchronised lyrics

### v0.8.5

- Stable internal player with cover, seeking and persistent controls
- Editable queue, two shuffle modes and repeat modes
- Media-library playback and improved Apple Music album matching
- Artist biographies, album descriptions and artist images

### v0.8.4

- Synchronised and unsynchronised lyrics model
- Embedded lyrics, LRC files and LRCLIB cache
- Confirmed lyrics embedding with preview and recovery

### v0.8.3

- Combined MusicBrainz/Discogs catalogue
- Local Discogs cache, artist, label and relationship views

The complete history is available in the [changelog](docs/CHANGELOG.md).

## Roadmap

v0.8.5 completed the stable player milestone. v0.8.6 extends queue handling,
lyrics display and Windows media integration. See the
[roadmap](docs/ROADMAP.md) for upcoming work and older milestones.

## License

See [LICENSE](LICENSE).
