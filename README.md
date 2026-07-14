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
