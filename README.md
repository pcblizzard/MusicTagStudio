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


### Verbesserungen in v0.6.4

- Vier parallele FFmpeg-Analysen auf geeigneten Systemen
- Dauerhafter Analyse-Cache für unveränderte Dateien
- Differenzierte True-Peak-Hinweise statt vollflächiger Warnzeilen
- Durchschnittliche Album-Bitrate und durchschnittliche Album-Lautheit
- Album-ReplayGain und Album-Peak in der Vergleichsansicht
- Erster Album-Gesundheitswert
- Analyseverlauf mit Cache-, Erfolgs- und Fehlermeldungen


### Verbesserungen in v0.6.5

- Realistischere True-Peak-Einordnung: bis 1 dBTP unauffällig
- Gesundheitswert wird bei leicht erhöhten Peaks deutlich weniger streng bewertet
- Sichtbare Cache-, Neuberechnungs- und Zeitstatistik
- Lesbareres Analyseprotokoll
- Fortschrittsdialog beim Schreiben von ReplayGain-Tags
- Einstellbare Anzahl paralleler FFmpeg-Analysen


### Verbesserungen in v0.6.6

- Qualitätsbewertung für Cover von 0 bis 100
- MD5-Vergleich zwischen vorhandenem Master und Online-Covern
- Anzeige identischer Inhalte, unterschiedlicher Auflösungen und abweichender Bilder
- Automatische Empfehlung des besten Covers
- Mehrere ausgewählte Alben können gemeinsam verarbeitet werden
- Vorhandene Master-Cover werden ohne erneuten Download wiederverwendet
- Fehler eines Albums stoppen die Verarbeitung der übrigen Alben nicht
