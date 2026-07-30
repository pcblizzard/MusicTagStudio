# MusicTagStudio

**English** | [Deutsch](README.de.md)

MusicTagStudio is a metadata editor, music catalogue and local audio player
for Windows. It connects local audio files with MusicBrainz, Discogs,
Apple Music, Deezer, TheAudioDB, Cover Art Archive and LRCLIB.

Current development version: **v0.8.6-alpha30**

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
- Apple Music, TIDAL and Spotify album-availability checks
- Cached streaming availability across views and application restarts
- TIDAL browser login with OAuth 2.0, PKCE and automatic token refresh
- TIDAL and Spotify credentials stored in the operating-system credential vault

### Lyrics

- Read embedded lyrics and local LRC files
- Support synchronised and unsynchronised lyrics
- Search LRCLIB and cache results locally
- Find a song from a remembered lyric fragment, searching local cached/LRC
  lyrics first and Genius as an optional online extension
- Store the optional Genius Client Access Token in the operating-system
  credential vault; Genius results link to the original page and are not
  scraped for full lyrics
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
- Standard or Apple Music-inspired visual preset
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
| TIDAL | Authenticated album-availability checks and catalogue links |
| Spotify | Authenticated album-availability checks and catalogue links |
| Deezer | Additional live artist suggestions |
| TheAudioDB | Localised artist biographies and album descriptions |
| Cover Art Archive | Additional cover candidates |
| LRCLIB | Synchronised and unsynchronised lyrics |

Online sources are used only for the purposes listed above. Qobuz, Amazon
Music and YouTube Music are not currently integrated as catalogue or
streaming providers.

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

Windows and Python 3.12–3.14 are required (**Python 3.13 or 3.14** recommended;
3.12 and 3.14 are covered by CI). Avoid pre-release Python builds (e.g. 3.15
betas), as PySide6 does not yet provide wheels for them.

```powershell
git clone https://github.com/pcblizzard/MusicTagStudio.git
cd MusicTagStudio
py -3.14 -m pip install --upgrade pip
py -3.14 -m pip install -e .
py -3.14 -m musictagstudio.main
```

Audio analysis, ReplayGain and acoustic fingerprinting need `ffmpeg`,
`ffprobe` and `fpcalc`. All other tagging, catalogue, lyrics and player
features work without them.

**Recommended** – fetch the tools once into `tools/` (the app finds them there
automatically, no `PATH` needed):

```powershell
py -3.14 scripts/fetch_tools.py
```

This places `ffmpeg.exe`, `ffprobe.exe` and `fpcalc.exe` under `tools/`
(git-ignored). A portable/setup build simply ships that folder, so end users
don't have to install anything.

Alternatively install FFmpeg system-wide (the `PATH` fallback then applies):

```powershell
winget install --id Gyan.FFmpeg --exact
```

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
py -3.14 -m pip install -e ".[dev]"
py -3.14 -m pytest
py -3.14 -m ruff check src tests
py -3.14 -m mypy
py -3.14 scripts/release_check.py
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

### v0.8.6-alpha30

- ISRC enrichment: look up missing tags (genre/year/label/composer) precisely by
  ISRC at MusicBrainz and Deezer, filling only empty fields
- Transcode detection: the authenticity banner estimates the source bitrate of a
  lossy origin from the spectral cutoff
- Fix: local albums shown as "not present" when the folder/tag title differed
  from the catalogue title by an edition suffix or a leading article; matching is
  now tolerant. Wording unified to "Locally present"/"Not present locally"
- Cover: Apple no longer claims a fixed 3000×3000 before download; the real size
  is measured on load
- BPM saved as a tag now also for WavPack, Monkey's Audio (APE) and WMA
- BPM detection runs fully in the background (large libraries stay responsive)
- "Play results"/"Add to queue" buttons play the current filter result (e.g. all
  favorites or all tracks around 95 BPM) directly as a queue
- Optional multiprocessing for audio analysis (experimental, with a clear
  instability note)
- Clearer TIDAL settings: availability login and exact-quality login are now
  labelled separately (internal attribute-name clash fixed)

### v0.8.6-alpha29

- BPM detection saved as a tag (FLAC/Vorbis, MP3, MP4) and a "Detect BPM" batch
  action; BPM filter in the tagger ("show tracks around 95 BPM")
- Favorites filter ("favorites only") in the tagger
- More readable purchase hint; visible "slower" note for exact album gain

### v0.8.6-alpha28

- Audio format conversion (MP3/AAC/Opus/FLAC/ALAC) via bundled FFmpeg (PyAV),
  copies tags and cover
- Exact TIDAL quality (opt-in): connect a TIDAL account and show an album's real
  bit depth / sample rate next to the tier
- Tagger genre/artist filter bar; library quality statistics dialog
- BPM detection (onset flux + autocorrelation) and a "Playback" now-playing view
  with large cover, info, BPM and controls (detachable window)
- Favorites (heart) and listening statistics (time per track/artist/album/genre)

### v0.8.6-alpha27

- Detailed per-track audio metrics (peak/RMS/dynamic range/clipping/spectral
  cutoff, per channel) with a new "Track details" tab
- Fake hi-res detection: authenticity verdict from spectral cutoff and edge
  shape, plus a fixed 96 kHz spectrogram reference axis and channel toggle
- True header bit depth; movable, persisted analysis columns
- Faster analysis (single decode) and a fast album gain/peak mode
- "Duplicates" view (quality-based keep-best, recycle-bin delete) and
  "Auto-tag" (batch tagging above a confidence threshold)
- Undo now survives a restart; history dialog shows a field-level report
- AcoustID identification enabled; provider catalog sizes shown
- Premium purchase buttons per duration with licence expiry display

### v0.8.6-alpha12

- Dedicated queue window with drag-and-drop and multi-selection
- Append local albums to an existing queue
- Global media keys and Windows system media display
- Karaoke display for synchronised lyrics
- Safer concurrent Discogs and SQLite cache access
- Consistent provider errors and local filename matching
- Ruff checks and CI coverage for Python 3.12 and 3.13
- Application-wide Apple/iTunes request pacing and bounded 429 retries
- Full Ruff `F` checks and removal of confirmed unused imports
- Separate appearance mode and visual preset
- Apple Music-inspired light and graphite-dark palettes
- Neutral table selections and calmer headers in the light preset
- Consistent graphite borders, inputs and surfaces in the dark preset
- Settings page clears unrelated sidebar selections and keeps its status state
- Slightly clearer card boundaries in the light Apple-inspired preset
- Live title and artist preview for all featured-artist handling modes
- Gradual mypy checks for 26 domain, cache, provider, lyrics and player modules
- Targeted type checking in CI on Python 3.12 and 3.13
- Defensive handling of unexpected numeric values in MusicBrainz responses
- Last streaming-availability check shown immediately and after cache reloads
- Authenticated TIDAL and Spotify album checks with direct catalogue links
- Secrets stored in the operating-system credential vault instead of config files

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

MusicTagStudio is licensed under the
[GNU General Public License v3.0 or later](LICENSE)
(`GPL-3.0-or-later`).

Copyright © 2026 Michael ([pcblizzard](https://github.com/pcblizzard)).
