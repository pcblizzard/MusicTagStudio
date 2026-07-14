# MusicTagStudio

MusicTagStudio ist ein vorsichtiger, vorschauorientierter Metadaten-Editor für FLAC, MP3, Ogg Vorbis, Opus und M4A/MP4.

## Start

```powershell
python -m pip install -e .
python -m pytest
python -m musictagstudio.main
```

## Cover-Workflow

- Master im Albumordner: `Albumkünstler - Album.front.<ext>`
- Eingebettet: 1000 px, JPEG, Qualität 100
- Künstlerordner: `Albumkünstler - Album_400px.jpg`, 400 px, Qualität 80
- Coverquellen und Zielordner-Ebene werden unter **Einstellungen → Optionen** gespeichert.


## Audio-Analyse

MusicTagStudio kann eine vorhandene lokale FFmpeg-Installation automatisch erkennen.

Die Analyse umfasst derzeit:

- Codec, Container, Abtastrate, Bittiefe, Kanäle, Bitrate und Dauer
- integrierte Lautheit in LUFS
- Loudness Range
- True Peak
- vorsichtiger Clipping-Hinweis
- ReplayGain Track Gain und Track Peak
- optionales Album-ReplayGain
- technischer Albumvergleich mit Abweichungsanzeige

ReplayGain wird zunächst berechnet und nur nach ausdrücklicher Bestätigung in die Dateien geschrieben.
