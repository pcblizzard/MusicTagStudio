# MusicTagStudio 0.8.6-alpha25

## Weiterer UI-Feinschliff und nachvollziehbare Fehler

- **Rückgängig/Wiederholen** nutzen jetzt SVG-Icons statt der Text-Pfeile
  „↶"/„↷".
- Die Status-Ampel in der Veröffentlichungs-Liste erscheint als farbiger
  Punkt-Icon (grün/orange/grau) statt als Emoji-Zeichen.
- Bisher stumm verschluckte Fehler (Cover-Laden, WavPack-Tags,
  TIDAL-Anmeldung) hinterlassen jetzt eine Log-Spur, ohne den Nutzer mit
  zusätzlichen Meldungen zu stören.

## Einheitliche Play/Pause-Icons in den Vorschau-Knöpfen

- Die Vorschau-Knöpfe in der Medienbibliothek und im Direkt-Album-Dialog nutzen
  jetzt dieselben SVG-Play/Pause-Icons wie die Wiedergabe-Leiste, statt der
  bisherigen Text-Symbole „▶"/„⏸" – konsistentes, theme-gerechtes Erscheinungsbild.

## Einheitlicher Fehlerkanal für die Wiedergabe

- Fehler beim Abspielen (z. B. nicht gefundene oder defekte Datei) überschreiben
  nicht länger den angezeigten Titel in der Wiedergabe-Leiste, sondern erscheinen
  als transiente Meldung in der App-Statusleiste – konsistent mit den übrigen
  Statusmeldungen und nach einigen Sekunden automatisch wieder ausgeblendet.

## Warteschlange bleibt über Neustarts erhalten

- Die Wiedergabe-Warteschlange (Titelliste und aktueller Titel) wird beim
  Beenden gespeichert und beim nächsten Start wiederhergestellt – bewusst
  **pausiert**, es wird also nichts automatisch abgespielt.
- Nicht mehr vorhandene Dateien werden beim Wiederherstellen still
  übersprungen; sehr große Warteschlangen werden auf 500 Titel begrenzt, damit
  die Einstellungsdatei nicht aufgebläht wird.
- Cover-Bilder werden nicht mitgespeichert, sondern beim Laden wieder aus der
  Datei gelesen.

## Diskografie: keine Feature-Alben, korrekte Vinyl-Tracknummern

- Alben, auf denen der gesuchte Künstler nur als Gast/Feature auftritt
  (Discogs-Rolle „Appearance“/„TrackAppearance“) oder nur Produktions-/Remix-
  Credits hat, erscheinen nicht mehr in dessen Diskografie – ein Juse-Ju-Album
  mit einem Danger-Dan-Feature landet also nicht mehr unter Danger Dan.
- Vinyl-Seitenangaben („A1“, „B2“ …) wurden bisher nur anhand der Zahl
  gelesen, sodass die B-Seite wieder bei Track 1 begann. Solche Positionen
  werden jetzt fortlaufend nummeriert, damit sich keine Tracknummern doppeln.

## Track-Vorschau: richtige Zuordnung und Titelanzeige

- Die 30-Sekunden-Vorschauen werden jetzt über den (normalisierten) Titel
  zugeordnet statt über (Disc, Tracknummer). Bei Discogs-Releases mit
  mehreren Medien/Seiten liefen die Tracknummern doppelt („01“ mehrfach),
  wodurch die falsche Vorschau abgespielt wurde – das ist behoben.
- Der Titelabgleich ignoriert feat.-Angaben und Klammerzusätze
  („7Eleven (feat. …)“ passt zu „7Eleven“).
- Die Wiedergabe-Leiste zeigt beim Wechsel auf eine andere Vorschau sofort
  den neuen Titel an (vorher blieb der zuvor gespielte Titel stehen).

## Aufgeräumte Oberfläche: Nav-Icons, gruppiertes Detail-Panel, Status-Chips

- Die Navigationsleiste links bekommt einheitliche SVG-Icons
  (Startseite/Tagger/Medienbibliothek/Audio-Analyse/Bibliotheksprüfung sowie
  „Song über Text finden") in der Palette-Farbe.
- Das Detail-Panel der Medienbibliothek ordnet die Knöpfe jetzt in klare
  Gruppen: **Prüfen** (Streaming/Qualität), **Auf Dienst öffnen**
  (Apple Music/TIDAL/Spotify) und **Lokal** (im Tagger öffnen/Warteschlange).
- Die lokale Verfügbarkeit erscheint als farbiger Status-Chip
  (grün „Lokal verfügbar", orange „Quelle nicht erreichbar",
  grau „Nicht vorhanden") statt als Fließtext.
- Ein neuer Smoke-Test prüft, dass alle Werkzeugleisten-Knöpfe eindeutige,
  nicht-leere Beschriftungen und keine doppelten Tooltips haben – so fällt ein
  Beschriftungsfehler künftig sofort auf.

## Zufallswiedergabe: eigenes Icon je Modus

- „Mit Verlauf“ und „Immer neu auslosen“ teilten sich in der Wiedergabe-Leiste
  dasselbe Symbol. „Immer neu auslosen“ bekommt jetzt ein Punkt-Badge (analog
  zum Punkt bei „ein Titel wiederholen“), sodass sich die beiden Modi optisch
  unterscheiden.

## Apple-Album per Link direkt im Batch-Vergleich laden

- Erkennt Apple Music ein Album nicht (die iTunes-Suche indexiert manche
  Alben nicht), bietet der Batch-Vergleich jetzt ein Eingabefeld für den
  Apple-Music-Link beziehungsweise die Album-ID.
- Nach dem Einfügen wird die offizielle Trackliste über die Lookup-API
  geladen, den lokalen Titeln positionsrichtig zugeordnet und die
  Apple-Music-Spalte ohne erneuten Durchlauf aktualisiert.
- Der Abruf läuft außerhalb der Oberfläche; ein Statustext meldet Erfolg,
  Fehler und die Zahl der zugeordneten Titel.
- Die Änderungsvorschau nennt jetzt eindeutig die Zahl der Feldänderungen
  und der betroffenen Titel (etwa „56 Änderungen an 9 Titeln werden
  geschrieben“) statt nur einer Gesamtzahl.
- Enthält der Batch-Vergleich keine tatsächlichen Änderungen (das Album ist
  bereits vollständig getaggt), erklärt „Ausgewählte Werte speichern“ dies
  jetzt, statt ohne Rückmeldung nichts zu tun.
- Ein Feld gilt nur noch als „Ergänzt“, wenn der vorgeschlagene Wert
  tatsächlich vom vorhandenen abweicht. Entspricht eine Zusatzquelle bereits
  dem lokalen Wert, bleibt die Auswahl auf „Lokal“ und zeigt keinen
  irreführenden Änderungshinweis mehr an.

## Externe Werkzeuge werden mitgeliefert statt manuell installiert

- FFmpeg/ffprobe (Audio-Analyse, ReplayGain, Spektrogramm) und fpcalc
  (Fingerabdruck) liegen jetzt einheitlich unter `tools/` und werden von der
  App **zuerst dort** gesucht (PATH bleibt Fallback). Ein Portable-/Setup-Build
  kann den Ordner mitliefern, sodass Endnutzer nichts installieren müssen.
- Neues Skript `scripts/fetch_tools.py` lädt die Werkzeuge einmalig nach
  `tools/` (FFmpeg von gyan.dev, fpcalc von acoustid).
- `tools/` ist gitignoriert – die großen Binärdateien blähen das Repository
  nicht auf; auch die zuvor eingecheckte `fpcalc.exe` wurde aus Git entfernt.
- Auch die WavPack-ffprobe-Fallback-Leseroutine nutzt jetzt die mitgelieferte
  ffprobe-Version statt ausschließlich den PATH.

## Rückgängig-Verlauf spart massiv Speicherplatz

- Der Verlauf sicherte bisher bei **jedem** Tag-/Cover-Vorgang **komplette
  Kopien der Audiodateien** (before + after). Bei großen, verlustfreien
  Dateien wuchs `.musictagstudio/history` so schnell auf viele Gigabyte.
- Jetzt wird pro Datei nur der Zustand **Tags + Cover** gesichert – Cover
  dedupliziert als Blob (gleiches Cover nur einmal). Beim Rückgängigmachen
  werden die Tags zurückgeschrieben und das Cover nur dann neu eingebettet
  bzw. entfernt, wenn es sich tatsächlich unterscheidet.
- Aus zuvor mehreren Gigabyte pro Vorgang werden wenige Kilobyte. Undo/Redo
  von Tag-Änderungen schreiben die Datei gar nicht mehr komplett neu.
- Neu: `remove_cover()` zum Entfernen eines eingebetteten Covers (für den
  Undo-Fall „vorher war kein Cover vorhanden").

## Fehlerbehebung: „Über dieses Album" zeigte rohes JSON

- Bei manchen Apple-Music-Alben wurde in „Über dieses Album" das rohe
  JSON-LD statt der Beschreibung angezeigt. Ursache: Apple bettet den
  JSON-LD-Block innerhalb der Editorial-Marker ein, und der Textparser hatte
  den Script-Inhalt als Text eingesammelt.
- Der Parser überspringt jetzt `<script>`/`<style>`-Inhalte, und JSON-artige
  Fundstücke werden zusätzlich verworfen. Angezeigt wird nun die saubere
  Album-Beschreibung.

## GUI-Refresh: einheitliche Icons in der Wiedergabe-Leiste

- Die gemischten Emoji (🔀 ◀ ▶ ▶| ↻ ☷ 🔊) und das „Ⅱ" der Wiedergabe-Leiste
  weichen einem **einheitlichen, monochromen SVG-Iconsatz** (Zufall, Zurück,
  Wiedergabe/Pause, Weiter, Wiederholen, Warteschlange, Lautstärke/Stumm).
- Die Icons passen sich dem hellen/dunklen Theme an (sie werden in der
  Palette-Farbe gerendert und bei Theme-Wechsel neu gezeichnet).
- Das reine Text-Label „Lautstärke" entfällt zugunsten des Lautsprecher-Icons.
- Neues Modul `icons.py` mit den Inline-SVG-Icons (kein externes Asset-/CDN-
  Handling).

## „Song über Text finden" in die Seitennavigation verschoben

- Der Knopf „Song über Text finden" sitzt jetzt in der linken Navigationsleiste
  (unter „Bibliotheksprüfung") statt in der Tagger-Werkzeugleiste. Die
  Werkzeugleiste ist dadurch wieder auf zwei saubere Vierer-Reihen aufgeräumt.

## Fehlerbehebung: vertauschte Beschriftungen der Tagger-Knöpfe

- Nach Aufnahme des Knopfes „Nach Klang identifizieren" waren die
  Beschriftungen der Tagger-Werkzeugleiste verrutscht (u. a. „BBCode-Text
  erstellen" doppelt, „Mehr vom Künstler" fehlte, falsche Tooltips). Ursache
  war eine positionsbasierte Umbenennung der Knöpfe im Layout.
- Jeder Knopf trägt seinen Text und Tooltip jetzt fest von der Erstellung; das
  Layout ordnet nur noch an. Dadurch bleiben Beschriftung, Tooltip und Aktion
  immer am selben Knopf – auch wenn später weitere Knöpfe hinzukommen.

## Nach Klang identifizieren (akustischer Fingerabdruck / AcoustID)

- Neuer Knopf **„Nach Klang identifizieren"** im Tagger: Er berechnet den
  akustischen Fingerabdruck des ausgewählten Titels (Chromaprint/`fpcalc`),
  fragt AcoustID ab und lädt die passenden MusicBrainz-Metadaten. Die Treffer
  erscheinen im gewohnten Vergleichsdialog zum Prüfen und Übernehmen — ideal
  für falsch oder gar nicht getaggte Dateien.
- `fpcalc` wird bevorzugt aus `providers/vendor/` genutzt, sonst aus dem
  System-PATH; ein eigener Pfad ist in den Einstellungen hinterlegbar.
- Der AcoustID-Key wird als App-Key mitgeliefert und ist pro Nutzer in den
  Einstellungen überschreibbar (`acoustid_api_key`).
- Neuer MusicBrainz-Recording-Lookup per MBID (`lookup_recording_by_id`)
  wandelt einen AcoustID-Treffer in einen vollständigen Metadaten-Vorschlag.
- Fehlen `fpcalc` oder Key – oder lehnt AcoustID den Key ab –, erscheint eine
  verständliche Meldung (inkl. der AcoustID-Fehlerursache) statt eines
  Absturzes.

## Wiedergabe-Knopf spielt lokale Titel in voller Länge

- Der Knopf in der Trackliste ist jetzt kontextabhängig: Liegt der Titel lokal
  vor, spielt ein Klick den **vollen Song** über die normale Wiedergabe-Leiste
  (wie ein Doppelklick). Nur bei nicht vorhandenen Titeln wird die
  30-Sekunden-Vorschau abgespielt.
- Die Spalte heißt jetzt „Wiedergabe"; der Tooltip erklärt je Zeile, ob voller
  Titel oder Vorschau abgespielt wird.
- Liegt ein Album vollständig lokal vor, entfällt die Vorschau-Auflösung
  komplett.

## 30-Sekunden-Track-Vorschau für nicht-lokale Alben

- Jeder Albumtrack lässt sich jetzt vorab anhören, ohne die Datei zu besitzen:
  ein ▶-Knopf pro Track spielt die offizielle 30-Sekunden-Vorschau ab
  (Apple `previewUrl` bzw. Deezer `preview` – keine Anmeldung, kein Scraping).
- Verfügbar an zwei Stellen:
  - **Direkt-Album-Dialog** (Album per Link/ID laden): spielt die Vorschau des
    jeweils zugeordneten Album-Tracks.
  - **Medienbibliothek-Trackliste**: die Vorschauen werden im Hintergrund über
    Deezer aufgelöst und den Titeln positionsrichtig zugeordnet.
- Ein eigener, schlanker Vorschau-Player sorgt dafür, dass die normale
  Wiedergabe-Queue der lokalen Bibliothek unberührt bleibt; es läuft immer nur
  eine Vorschau, eine neue stoppt die vorherige.
- Der ▶-Knopf ist nur aktiv, wenn tatsächlich eine Vorschau vorliegt
  (MusicBrainz/Discogs liefern keine).
- Während eine Vorschau läuft, zeigt die Medienbibliothek „▶ Vorschau läuft:
  <Titel>" im Status an.
- Die untere Wiedergabe-Leiste spiegelt die laufende Vorschau: Titel, Position
  und die ~30-Sekunden-Dauer werden angezeigt, Wiedergabe/Pause und die
  Suchleiste steuern die Vorschau. Die lokale Wiedergabe wird dafür nur
  pausiert und nach der Vorschau unverändert wiederhergestellt; die
  Warteschlange bleibt erhalten (Queue-/Titelsprung-Knöpfe sind während der
  Vorschau deaktiviert).
- Neue Einstellung „Vorschau-Quelle" (Deezer oder Apple Music) bestimmt, über
  welchen Anbieter die Vorschauen in der Medienbibliothek aufgelöst werden.
- Der veraltete Hinweis „Qobuz und Deezer folgen in späteren Ausbaustufen" in
  der Streaming-Prüfung wurde entfernt.
- Fehlerbehebung: Bei Alben mit mehreren Discs (sich wiederholenden
  Tracknummern) wurde die ⏸-Markierung fälschlich auf mehreren Zeilen
  gleichzeitig angezeigt. Die spielende Zeile wird jetzt zeilengenau
  hervorgehoben, unabhängig von gleichen Vorschau-URLs.
- Fehlerbehebung: Die Vorschau-CDNs (Apple/Deezer) wiesen den Standard-
  User-Agent des Qt-/ffmpeg-Backends mit HTTP 403 ab, sodass keine Vorschau
  abspielte. Die Vorschau wird nun mit einem Browser-User-Agent in eine
  temporäre Datei geladen und lokal abgespielt. Während des Ladens erscheint
  ein Hinweis, bei Fehlern eine verständliche Meldung.

## Deezer als vollwertige Metadatenquelle

- Deezer ist jetzt als eigene Quelle auswählbar und erscheint mit eigener
  Spalte im Vergleich. Genutzt wird die offizielle, öffentliche Deezer-API
  (`api.deezer.com`) ohne Anmeldung – eine saubere, dokumentierte Quelle.
- Deezer liefert vollständige Album-Tracklisten inklusive **ISRC**, Label,
  Jahr, Genre sowie Track- und Disc-Positionen. Besonders wertvoll: ISRC,
  das die Apple-Lookup-Schnittstelle nicht bereitstellt.
- Der Batch-Vergleich lädt das Deezer-Album album-zentriert (wie Apple und
  MusicBrainz) und ordnet die Titel positionsrichtig zu; als Rückfall dient
  eine titelweise Deezer-Suche.
- Die Vergleichsdialoge leiten ihre Spalten jetzt aus einer zentralen
  Quell-Liste ab. Neue Quellen lassen sich dadurch an einer Stelle ergänzen,
  ohne feste Spaltenindizes anzupassen.
- Qobuz und Amazon Music wurden geprüft, sind aber ohne Nutzer-Anmeldung
  nicht sauber anzubinden (Qobuz sperrt seine Metadaten-API hinter Login,
  Amazon Music liefert ohne Login keine Katalogdaten) und bleiben daher
  vorerst außen vor.

## Apple-Music-Websuche findet nicht indexierte Alben automatisch

- Die iTunes-Such-API indexiert nicht jedes Album (z. B. „Das ist alles von
  der Kunstfreiheit gedeckt" von Danger Dan). Findet sie kein sicheres
  Ergebnis, durchsucht MusicTagStudio jetzt zusätzlich die öffentliche
  Apple-Music-Weboberfläche (`music.apple.com`), deren eingebettetes JSON den
  vollen Katalog abdeckt. Die gefundene Collection-ID speist die bestehende,
  verlässliche Lookup-Trackliste.
- Es werden ausschließlich öffentlich ausgelieferte Metadaten gelesen – kein
  Login, kein Token, keine Musikdaten. Die Web-Anfrage nutzt denselben
  Anfrageabstand und Antwort-Cache wie die übrigen Apple-Abfragen.
- Neuer Schalter „Apple-Music-Websuche als Fallback nutzen" in den
  Einstellungen (Standard: an) und `apple_web_search_enabled` in der
  `[network]`-Konfiguration.
- Der Batch-Albumvergleich nutzt die Websuche als eigene Fallback-Stufe:
  Findet die iTunes-Suche das Album nicht, wird die Collection-ID über die
  Websuche ermittelt, bevor die MusicBrainz-Brücke greift. Damit füllt sich
  die Apple-Music-Spalte auch für nicht indexierte Alben automatisch.
- Das manuelle Einfügen eines Apple-Links bleibt als Rückfallweg bestehen, ist
  für solche Alben aber meist nicht mehr nötig.

## Schnelleres Schreiben von Tags und Covern

- Das Speichern der Tags eines Albums läuft jetzt parallel statt Datei für
  Datei nacheinander. Da Datei-I/O den GIL freigibt, sinkt die Wartezeit für
  ein ganzes Album spürbar; die Oberfläche wird erst nach Abschluss aller
  Schreibvorgänge auf dem Hauptthread aktualisiert.
- Auch das Einbetten eines neuen Albumcovers erfolgt für alle Titel parallel
  – gerade bei FLAC-Dateien (die beim Speichern komplett neu geschrieben
  werden) ist das deutlich schneller.
- Beim Schreiben von MP3-Tags entfällt ein überflüssiger vollständiger
  Datei-Parse (`MP3(path)`), dessen Ergebnis nie verwendet wurde.
- Ein Fehler bei einer einzelnen Datei bricht den Album-Durchlauf nicht mehr
  ab; die übrigen Dateien werden trotzdem gespeichert und der Fehler pro
  Titel gemeldet.

# MusicTagStudio 0.8.6-alpha24

## Parallele Albumabfragen und Cache-Steuerung

- Der Apple-Music- und der MusicBrainz-Albumpfad laufen beim Batch-Taggen
  jetzt gleichzeitig. Da beide getrennte Rate-Limit-Sperren nutzen, sinkt die
  Wartezeit spürbar, ohne die Reihenfolge oder Auswahl der Vorschläge zu
  verändern.
- Die Einstellungen bieten unter „Online-Kataloge“ einen Knopf
  „Provider-Cache leeren“. Er verwirft die zwischengespeicherten Apple- und
  MusicBrainz-Antworten, sodass Alben bei Bedarf neu abgefragt werden.

# MusicTagStudio 0.8.6-alpha23

## TIDAL-Verbindung bleibt gültig

- Die Auffrischung des TIDAL-Zugriffstokens sendet jetzt die erforderliche
  `client_id`. Bisher meldete TIDAL nach Ablauf des Tokens „HTTP 400:
  invalid_request, Missing parameters: client_id“, und die
  Verfügbarkeitsprüfung schlug fehl.
- Der Antwort-Cache der Anbieter wird in Tests in ein temporäres Verzeichnis
  umgeleitet und verschmutzt das Projekt-Cache-Verzeichnis nicht mehr.

# MusicTagStudio 0.8.6-alpha22

## Deutlich schnelleres Taggen

- Antworten von Apple/iTunes und MusicBrainz werden lokal zwischengespeichert.
  Wird dasselbe Album erneut getaggt, stammen Such- und Lookup-Ergebnisse aus
  dem Cache und erscheinen nahezu sofort.
- Findet die Apple-Albumsuche ein Album nicht, entfällt die aufwendige
  Einzeltitel-Suche über alle Titel. Sie fände ohnehin nur fremde Ausgaben.
- Der US-Store wird bei der Einzeltitelsuche nur noch als Rückfallebene
  abgefragt, wenn der bevorzugte Store nichts liefert.
- Die MusicBrainz-Brücke zur Apple-collectionId prüft nur noch die beste
  Release-Übereinstimmung und stellt damit höchstens eine Zusatzanfrage.
- Der Standardabstand zwischen Apple-Anfragen wurde von 1,5 auf 1,0 Sekunden
  gesenkt; er bleibt in den Einstellungen zwischen 0,5 und 10 Sekunden
  wählbar.

# MusicTagStudio 0.8.6-alpha21

## Spektrogramm und zuverlässigere Apple-Albumzuordnung

- Die Audio-Analyse zeigt in einem eigenen Reiter „Spektrogramm“ den Zeit-
  und Frequenzverlauf des markierten Titels. Das Bild wird per FFmpeg
  außerhalb der Oberfläche erzeugt und je Datei zwischengespeichert.
- Einzeltitel-Treffer aus fremden Alben, etwa aus einer Compilation, dürfen
  keine abweichende Track- oder Discnummer mehr in einen Vorschlag einsetzen,
  solange der Albumname nicht übereinstimmt.
- Findet die iTunes-Suche ein Album nicht, ermittelt MusicBrainz über seine
  Apple-Music-Verweise die collectionId. Damit lädt der vorhandene
  Lookup-Pfad die korrekte, positionsrichtige Trackliste.
- Der Batch-Vergleich weist ausdrücklich darauf hin, ein unsicher erkanntes
  Apple-Album über den Direkt-Album-Dialog per Apple-Music-Link zu laden.

# MusicTagStudio 0.8.6-alpha20

## Provider-Diagnose und steuerbare Anfrageabstände

- Discogs, TIDAL, Spotify und Genius können in den Einstellungen gemeinsam
  und ohne Offenlegung ihrer Zugangsdaten geprüft werden.
- Die Oberfläche unterscheidet nicht eingerichtete, gültige und
  fehlgeschlagene Zugänge und merkt sich den Zeitpunkt der letzten
  erfolgreichen Prüfung.
- Die Anfrageabstände für Apple/iTunes und Genius sind zwischen 0,5 und
  10 Sekunden einstellbar; die bisherigen Standardwerte bleiben 1,5 bzw.
  1,0 Sekunden.
- Genius ergänzt Albumdetails nur noch für die ersten fünf Treffer. Dadurch
  werden Textsuchen schneller und erzeugen deutlich weniger API-Anfragen.
- Die Debug-Info zeigt sichere Provider-Zustände, den gewährten TIDAL-Scope,
  die Anfrageabstände und die Größe des Streaming-Caches, niemals jedoch
  Tokens oder Client Secrets.

# MusicTagStudio 0.8.6-alpha19

## Stabilere Online-Anbieter und reproduzierbare Tests

- Genius-Anfragen besitzen jetzt ein gemeinsames Request-Pacing und beachten
  bei HTTP 429 die vom Anbieter angegebene Wartezeit.
- Das Ergebnislimit der kombinierten lokalen und Genius-Lyrics-Suche wird
  zuverlässig eingehalten.
- Parallele TIDAL-Abfragen teilen sich einen einzigen Token-Refresh. Eindeutig
  abgelehnte Refresh-Tokens werden aus dem sicheren Speicher entfernt.
- Der lokale TIDAL-Callback wartet bis zum tatsächlichen OAuth-Rückruf und
  wird nicht mehr durch Browser-Prefetches oder eine Favicon-Anfrage beendet.
- Ein unerwarteter Fehler eines Streaming-Anbieters verwirft nicht länger die
  bereits ermittelten Ergebnisse der übrigen Anbieter.
- Player-Tests verwenden keinen persönlichen, in Windows gespeicherten
  Zufallswiedergabemodus mehr.
- Redundante zweite Zwischenspeicher für lokale Titellängen wurden entfernt.

# MusicTagStudio 0.8.6-alpha18

## Info-, Mitwirkenden- und Debug-Dialog

- Das neue Menü „Info“ öffnet einen Dialog mit den Reitern „Über“,
  „Mitwirkende“ und „Debug-Info“.
- Der Über-Reiter nennt Version, Projektseite, Lizenzstatus und verwendete
  externe Programmschnittstellen.
- Der Mitwirkenden-Reiter nennt den Projektbetreuer `pcblizzard` und
  verlinkt die GitHub-Mitwirkenden.
- Die Debug-Info ermittelt Revision, Python-, PySide6- und Qt-Version,
  Betriebssystem, Architektur, Kernel und OpenSSL-Version dynamisch und kann
  vollständig in die Zwischenablage kopiert werden.
- Das Projekt steht nun ausdrücklich unter GPL-3.0-or-later. Lizenzhinweis,
  Copyright, Paketmetadaten, README und Info-Dialog wurden entsprechend
  vereinheitlicht.

# MusicTagStudio 0.8.6-alpha17

## Songs über erinnerte Textstellen finden

- Der Tagger besitzt den neuen Dialog „Song über Text finden“.
- Bereits zwischengespeicherte Lyrics und lokale LRC-Dateien werden zuerst
  durchsucht; lokale Treffer lassen sich direkt abspielen.
- Genius kann die Suche optional um Online-Treffer ergänzen. Dafür wird ein
  Client Access Token in der Anmeldeinformationsverwaltung des
  Betriebssystems statt in `config.toml` gespeichert.
- Genius-Ergebnisse zeigen Titel und Künstler und öffnen die jeweilige
  Originalseite. MusicTagStudio lädt oder kopiert darüber keine vollständigen
  Liedtexte.
- Der Suchdialog erklärt bei reinen Genius-Treffern, dass eine lokale
  Audiodatei nicht automatisch lokal gespeicherte Lyrics enthält. Die Spalte
  „Gefundene Textstelle“ besitzt zusätzlich einen erklärenden Tooltip.

# MusicTagStudio 0.8.6-alpha16

## Verständlichere Peak-Werte

- Die Spalten „True Peak“, „Peak-Hinweis“ und „Track Peak“ erklären ihre
  unterschiedlichen Messwerte jetzt direkt per Tooltip.
- Der True-Peak-Hinweis macht ausdrücklich darauf aufmerksam, dass ein
  unauffälliger Sample Peak mögliche Zwischenabtastspitzen nicht ausschließt.

# MusicTagStudio 0.8.6-alpha15

## Verlässliche TIDAL-Neuprüfung

- Erfolgreiche Streaming-Funde bleiben weiterhin sieben Tage im Cache.
- Negative Ergebnisse wie „nicht gefunden“ laufen bereits nach 30 Minuten
  ab, damit temporäre API-Antworten und Korrekturen nicht eine Woche lang
  verborgen bleiben.
- Die Streaming-Diagnose protokolliert Suchparameter, Kandidaten und die
  Anbieterentscheidung ohne Zugangsdaten in `logs/streaming.log`.

# MusicTagStudio 0.8.6-alpha14

## Aussagekräftige TIDAL-Diagnose

- TIDAL-Anfragen verwenden den in der aktuellen THIRD_PARTY-Referenz
  ausgewiesenen JSON:API-Medientyp `application/vnd.api+json`. Der veraltete
  TIDAL-v1-Medientyp führte am aktuellen Gateway irreführend zu HTTP 404.
- Schrägstriche in Suchbegriffen werden für den TIDAL-Ressourcenpfad als
  Leerzeichen übertragen und bis zu 20 Kandidaten ausgewertet. Dadurch wird
  unter anderem „Deja Vu 1/2“ eindeutig gefunden.
- Ein HTTP-404 nach erfolgreicher OAuth-Anmeldung wird nicht mehr als
  allgemeiner Suchfehler dargestellt.
- Die Medienbibliothek unterscheidet nun ausdrücklich zwischen einer gültigen
  TIDAL-Anmeldung und einem nicht verfügbaren öffentlichen Katalog-Endpunkt.
- Die Diagnose ist durch einen Regressionstest abgesichert.

# MusicTagStudio 0.8.6-alpha13

## TIDAL-Browseranmeldung

- TIDAL kann in den Einstellungen über den Browser mit MusicTagStudio
  verbunden und wieder getrennt werden.
- Die Anmeldung verwendet Authorization Code mit PKCE, den freigegebenen
  Scope `search.read` und die lokale Rückrufadresse
  `http://127.0.0.1:8765/tidal/callback`.
- Ein zufälliger `state`-Wert schützt die Rückgabe; der lokale Empfänger
  lauscht ausschließlich auf `127.0.0.1` und protokolliert keine Anfrage.
- Access- und Refresh-Token werden im Anmeldedatenspeicher des
  Betriebssystems abgelegt und Access-Token bei Bedarf automatisch erneuert.
- Die Katalogprüfung bevorzugt den verbundenen Benutzerzugang und verwendet
  den bisherigen Client-Credentials-Ablauf nur noch als Rückfalloption.
- PKCE, Tokenaustausch und die Auswahl des Benutzer-Tokens sind durch
  Regressionstests abgesichert.

# MusicTagStudio 0.8.6-alpha12

## TIDAL- und Spotify-Kataloge

- Die Medienbibliothek prüft ein Album parallel bei Apple Music, TIDAL und
  Spotify, sofern die jeweiligen Zugangsdaten eingerichtet sind.
- Treffer werden mit Künstler, Albumtitel, Jahr und Titelanzahl bewertet und
  nur oberhalb derselben konservativen Mindestübereinstimmung akzeptiert.
- Direkte TIDAL- und Spotify-Schaltflächen werden nur bei einem bestätigten
  Treffer aktiviert.
- Ergebnisse aller Anbieter verwenden den vorhandenen Sieben-Tage-Cache und
  zeigen den letzten Prüfzeitpunkt auch bei einem Apple-Nichttreffer.
- Client-IDs werden in den Einstellungen gespeichert; Client-Secrets liegen
  über `keyring` im Anmeldedatenspeicher des Betriebssystems und nicht im
  Klartext in der Konfigurationsdatei.
- Provider-, Cache- und Geheimnisablage sind durch neue Regressionstests sowie
  die erweiterte mypy-Prüfung abgesichert.
- Die TIDAL-Suche folgt dem von TIDAL beschriebenen zweistufigen JSON:API-
  Ablauf: zunächst Album-IDs suchen, anschließend Album- und Künstlerdaten
  gemeinsam laden. Nicht unterstützte verschachtelte `include`-Parameter
  werden nicht mehr verwendet.
- Providerfehler zeigen einen bereinigten HTTP-Status und die vom Anbieter
  gelieferte Fehlerbeschreibung, ohne Zugangsdaten offenzulegen.
- Der case-sensitive TIDAL-Suchpfad verwendet korrekt `/v2/searchResults`;
  Fehler nennen zusätzlich die betroffene Stufe Anmeldung, Suche oder
  Albumdetails.

# MusicTagStudio 0.8.6-alpha11

## Sichtbarer Streaming-Prüfzeitpunkt

- Nach jeder erfolgreichen Streaming-Prüfung wird sofort Datum und Uhrzeit der
  Prüfung angezeigt.
- Nach einem Ansichts- oder Programmneustart bleibt derselbe gespeicherte
  Prüfzeitpunkt sichtbar.
- Gespeicherte Ergebnisse werden weiterhin ausdrücklich als solche markiert.
- Der Apple-Mindestabstand bleibt unverändert bei 1,5 Sekunden.

# MusicTagStudio 0.8.6-alpha10

## Erweiterte statische Typprüfung

- Der mypy-Prüfumfang wächst von acht auf 20 klar abgegrenzte Module.
- Zusätzlich geprüft werden Apple-, MusicBrainz-, Deezer- und TheAudioDB-
  Provider, direkte Referenzen sowie weitere Lyrics-Bausteine.
- Unerwartete Zahlentypen in MusicBrainz-Antworten werden defensiv behandelt,
  anstatt ungeprüft an `int()` übergeben zu werden.
- Ein Regressionstest deckt gültige und unerwartete MusicBrainz-Zahlenwerte ab.
- Das Netzwerkverhalten und die verwendeten HTTPS-Endpunkte bleiben
  unverändert.

# MusicTagStudio 0.8.6-alpha9

## Schrittweises Type-Checking

- `mypy` ist Teil der Entwicklungsabhängigkeiten und kann über
  `python -m mypy` gestartet werden.
- Acht klar abgegrenzte Domain-, Cache-, Provider- und Player-Module werden
  zunächst statisch geprüft.
- Die gezielte Typprüfung läuft in der CI unter Python 3.12 und 3.13.
- Die Behandlung von `HTTPError.headers` im gemeinsamen Apple-HTTP-Modul ist
  für die unterschiedlichen Laufzeit- und Typisierungsvarianten abgesichert.
- Der Prüfumfang wird bewusst schrittweise erweitert, damit Qt- und
  Bibliotheks-Typisierungen nicht als unübersichtliches Gesamtpaket einfließen.

# MusicTagStudio 0.8.6-alpha8

## Feature-Künstler-Vorschau und Einstellungsnavigation

- „Einstellungen“ wurde auf Wunsch wieder aus der linken Hauptnavigation
  entfernt und bleibt über das Dateimenü sowie die Startseite erreichbar.
- Während die Einstellungsseite sichtbar ist, wird kein anderer
  Navigationspunkt fälschlich als aktiv dargestellt.
- Die Feature-Künstler-Auswahl zeigt live ein Beispiel für resultierenden
  Titel und resultierendes Künstlerfeld.
- Die Vorschau verwendet dieselbe Normalisierungslogik wie die tatsächliche
  Metadatenverarbeitung.
- Alle drei Modi – nur Künstlerfeld, Titel und Künstlerfeld sowie
  Quellschreibweise – sind durch UI-Regressionstests abgesichert.

# MusicTagStudio 0.8.6-alpha7

## Synchronisierte Einstellungsnavigation

- Einstellungen besitzen nun einen eigenen Eintrag in der linken Navigation.
- Beim Öffnen der Einstellungen werden sichtbarer Arbeitsbereich,
  Navigationsmarkierung und Statuszeile gemeinsam aktualisiert.
- Auch der initiale Startseitenzustand verwendet dieselbe zentrale
  Umschaltlogik und kann deshalb nicht mehr von der Sidebar abweichen.
- Die Kartenrahmen im hellen Apple-Preset wurden geringfügig verstärkt, ohne
  die ruhige helle Oberfläche aufzugeben.
- Regressionstests sichern den Start- und Einstellungszustand der Navigation.

# MusicTagStudio 0.8.6-alpha6

## Theme-Polishing

- Tabellenmarkierungen im hellen Apple-Preset sind neutraler und konkurrieren
  nicht mehr mit der roten Navigations- und Player-Akzentfarbe.
- Tabellenköpfe, Rasterlinien und Eingabefeldrahmen verwenden ruhigere,
  konsistente Grautöne.
- Das dunkle Preset ersetzt verbliebene bläuliche Rahmen durch neutrale
  Graphitfarben.
- Karten, Listen, Tabellen, Eingaben und Schaltflächen verwenden
  vereinheitlichte Rundungen.
- Scrollbars und Statusflächen wurden an die jeweilige Preset-Palette
  angeglichen.

# MusicTagStudio 0.8.6-alpha5

## Theme-Presets

- Der Helligkeitsmodus Automatisch/Hell/Dunkel und das visuelle Design sind
  jetzt getrennte Einstellungen.
- Das bisherige MusicTagStudio-Design bleibt unverändert als Standard erhalten.
- Ein zusätzliches Apple-Music-inspiriertes Preset bietet eine helle,
  zurückhaltende Oberfläche sowie ein graphitdunkles Design mit rotem Akzent.
- Auswahl, Speicherung und sofortige Anwendung erfolgen über den bestehenden
  Einstellungsbereich.
- Ungültige oder ältere Konfigurationen fallen sicher auf das Standarddesign
  zurück.
- Änderungsmarkierungen verwenden Palettenfarben und passen sich dadurch an
  beide Presets an.

# MusicTagStudio 0.8.6-alpha4

## Apple-Pacing und statische Prüfung

- Apple-/iTunes-JSON-Anfragen verwenden eine gemeinsame app-weite
  Mindestpause und verhindern damit ungebremste Request-Spitzen bei
  Varianten- und Track-Fallback-Suchen.
- HTTP 429 wird einmal anhand von `Retry-After` wiederholt; die Wartezeit ist
  auf 30 Sekunden begrenzt.
- Der Pacing-Lock wird vor dem Netzwerkzugriff freigegeben und blockiert keine
  parallel laufende Antwort.
- Direkte Apple-Song-/Album-ID-Abfragen verwenden denselben Mechanismus.
- Ruff prüft nun die vollständige `F`-Fehlerfamilie. Bestätigte ungenutzte
  Imports wurden entfernt; bewusst gehaltene Qt-Testreferenzen sind eng auf
  Tests begrenzt ausgenommen.

# MusicTagStudio 0.8.6-alpha3

## Stabilität und Entwicklungsqualität

- Discogs hält den globalen Pacing-Lock nicht mehr während Netzwerkzugriffen
  oder `Retry-After`-Wartezeiten.
- Gemeinsame Helfer liefern in direkter Albumsuche und Vorschlagsdienst
  dieselben Dateinamen-Titel und lokalen Tracklängen.
- Apple Editorial und TheAudioDB übersetzen Netzwerk- und Antwortfehler in
  einen einheitlichen `EditorialProviderError`.
- SQLite-basierte Lyrics-, Streaming- und Discogs-Caches warten begrenzt auf
  konkurrierende Schreibzugriffe.
- Apple-/iTunes-Anfragen verwenden die aktuelle Paketversion im User-Agent.
- Eine konservative Ruff-Prüfung erkennt kritische Syntax- und Namensfehler.
- Die CI testet Python 3.12 und 3.13.
- Zwei zuvor fehlende Helfer der direkten Apple-Song-ID-Abfrage wurden
  ergänzt und durch Regressionstests abgesichert.

# MusicTagStudio 0.8.6-alpha2.3

## Windows-Systemmedienanzeige

- Der laufende Titel erscheint mit Titel, Künstler und Album in der
  Windows-Systemmedienanzeige.
- Eingebettete beziehungsweise lokale Cover werden als Albumthumbnail
  bereitgestellt und hashbasiert im App-Cache wiederverwendet.
- Wiedergabe und Pause werden an Windows gemeldet.
- Die Schaltflächen der Windows-Mediensitzung steuern Play/Pause, Vor, Zurück
  und Stop.
- Ist Windows Runtime nicht verfügbar, bleibt der bisherige globale
  Medientasten-Controller als Fallback aktiv.
- Bei aktiver Systemmediensitzung wird der ältere Hotkey-Handler deaktiviert,
  damit ein Tastendruck nicht doppelt ausgeführt wird.
- Die Windows-Runtime-Pakete werden ausschließlich unter Windows installiert.

# MusicTagStudio 0.8.6-alpha2.2

## Statische und mitlaufende Lyrics

- Der Lyrics-Dialog bietet eine Auswahl zwischen Textansicht und Karaoke.
- Der Karaoke-Modus ist nur für synchronisierte Lyrics verfügbar.
- Die zur Playerposition gehörende Zeile wird hervorgehoben und automatisch
  mittig ins Sichtfeld gescrollt.
- Bei einem anderen oder nicht geladenen Player-Titel wird keine falsche Zeile
  markiert.
- Unsynchronisierte Lyrics bleiben automatisch in der bisherigen Textansicht.
- Die zuletzt gewählte Lyrics-Ansicht wird gespeichert.

# MusicTagStudio 0.8.6-alpha2.1

## Globale Windows-Medientasten

- Play/Pause, nächster Titel, vorheriger Titel und Stop lassen sich über
  Medientasten steuern.
- Unterstützt werden Windows-Hotkeys und `APPCOMMAND`-Ereignisse von
  Tastaturen, Headsets und Bluetooth-Geräten.
- Erfolgreiche globale Registrierungen funktionieren auch bei einem nicht
  fokussierten MusicTagStudio-Fenster.
- Bereits anderweitig belegte Tasten verhindern den App-Start nicht und werden
  im Anwendungsprotokoll vermerkt.
- Beim Schließen werden sämtliche globalen Hotkeys und nativen Ereignisfilter
  zuverlässig freigegeben.

# MusicTagStudio 0.8.6-alpha1

## Eigenständige Warteschlangenansicht

- Der Warteschlangenknopf öffnet ein eigenes, in der Größe gespeichertes Fenster.
- Titel lassen sich per Drag-and-drop umsortieren, ohne den laufenden Titel zu verlieren.
- Mehrere Titel können gemeinsam markiert und aus der Warteschlange entfernt werden.
- Einzelne Titel lassen sich sofort starten oder direkt hinter den laufenden Titel verschieben.
- Ein Doppelklick startet den gewählten Titel.
- Lokale Alben können aus der Medienbibliothek an eine bestehende Warteschlange angehängt werden.
- Der laufende Titel wird fett und mit Wiedergabesymbol hervorgehoben.

# MusicTagStudio 0.8.5

## Stabiler Player-Release

- Die Zufallswiedergabe mit Verlauf unterstützt nun einen echten Vorwärts- und Rückwärtsverlauf.
- Lautstärke, Stummschaltung, Wiederholungsmodus und Zufallsart bleiben nach Neustarts erhalten.
- Fehlende Dateien werden gemeldet und zugängliche Folgetitel automatisch geladen.
- Die Warteschlangenanzeige nennt ihre Titelanzahl und sämtliche Player-Schaltflächen besitzen verständliche zugängliche Namen.
- Zusätzliche Regressionstests sichern Zufallsrunden, Verlaufssprünge, Warteschlangenänderungen und fehlende Dateien ab.

# MusicTagStudio 0.8.5-beta

## Gespeicherter Playerzustand und bearbeitbare Warteschlange

- Lautstärke, Wiederholungsmodus und gewählte Zufallsart bleiben nach einem Neustart erhalten.
- Die Warteschlange lässt sich leeren; einzelne Titel können entfernt oder als Nächstes einsortiert werden.
- Nicht mehr erreichbare Audiodateien werden beim normalen Titelwechsel gemeldet und automatisch übersprungen.
- Der alternative Würfelmodus lost bei Vor und Zurück jeweils einen neuen Titel aus, ohne innerhalb einer Runde Titel zu wiederholen.
- Statusfarben der Audioanalyse verwenden im hellen Theme gut lesbare Pastelltöne.
- Informationszeilen der Bibliotheksprüfung erhalten keinen störenden dunklen Hintergrund mehr.

# MusicTagStudio 0.8.5-alpha3

## Player und Detailansicht

- Die Playerleiste zeigt Cover, Albumname und die aktuelle Warteschlange.
- Die Zufallswiedergabe bietet einen navigierbaren Verlauf und einen Modus, der bei Vor und Zurück jeweils neu auslost.
- Wiederholung eines Titels oder der gesamten Warteschlange ist verfügbar.
- Titel können direkt aus dem Warteschlangenmenü angesprungen werden.
- Die Leertaste schaltet Wiedergabe und Pause um, solange keine Texteingabe aktiv ist.
- Der aktuell wiedergegebene Titel wird im Tagger und in der Album-Trackliste hervorgehoben.
- Lange Künstlerbiografien und Albuminformationen lassen sich in einer eigenen, gut lesbaren Ansicht vollständig öffnen.
- Die Künstlerübersicht blendet die leere Trackliste aus; bei ausgewählten Veröffentlichungen erscheint sie wieder.
- Die Aufteilung der Tagger- und Medienbibliotheksbereiche wird über Neustarts hinweg gespeichert.

# MusicTagStudio 0.8.5-alpha2

## Medienbibliothek, Player und redaktionelle Informationen

- Lokale Titel lassen sich direkt aus der Album-Trackliste der Medienbibliothek per Doppelklick abspielen.
- Die gemeinsame Playerleiste übernimmt dabei die lokalen Titel des Albums als Warteschlange.
- Die Apple-Music-Albumsuche berücksichtigt Künstler, Titel, Jahr, Trackanzahl und Trackkonsens zuverlässiger.
- Bestätigte Streaming-Ergebnisse werden dienstübergreifend vorbereitet und für sieben Tage gespeichert.
- Ansichtswechsel lösen dadurch keine unnötigen erneuten Streaming-Prüfungen mehr aus.
- Künstler- und Albumsuche priorisieren exakte beziehungsweise plausible Treffer; Tippfehlerkorrekturen werden verständlich gekennzeichnet.
- Künstlerbiografien und Albuminformationen werden abhängig von App- oder Systemsprache auf Deutsch beziehungsweise Englisch dargestellt.
- Echte Apple-Music-Künstler-Heros werden in der Künstlerübersicht angezeigt; fehlt das Hero, dient das primäre Discogs-Künstlerbild als Fallback. Video- und sonstige Vorschaubilder bleiben ausgeschlossen.
- TheAudioDB dient als strukturierte Informationsquelle; fehlende deutsche Texte fallen sichtbar auf Englisch zurück.
- Eindeutig bestätigte Apple-Music-Alben können deren redaktionellen Albumtext als Fallback anzeigen.
- Der Apple-Extraktor unterstützt Beschreibungsblöcke, `HTML_TAG_START`/`HTML_TAG_END`, JSON-LD und entfernt ausgewählte Songparameter aus Albumlinks.
- Die Detailansicht zeigt kompaktere Quellenangaben und mehr gleichzeitig sichtbare Trackzeilen.
- Ein Bibliotheks-Refresh entfernt verwaiste Indexeinträge nicht mehr konfigurierter Musikquellen, behält eingerichtete Offlinequellen aber bei.

# MusicTagStudio 0.8.5-alpha1

## Lokaler Player – Grundlage

- Ausgewählte lokale Titel lassen sich im Tagger über „Titel abspielen“ oder per Doppelklick starten.
- Eine kompakte Playerleiste bleibt am unteren Fensterrand sichtbar.
- Wiedergabe/Pause, vorheriger und nächster Titel sowie eine Warteschlange aus der aktuellen Titelliste sind verfügbar.
- Position, Titeldauer, Suche innerhalb des Titels, Lautstärke und Stummschaltung werden unterstützt.
- Fehlende oder verschobene Audiodateien werden verständlich gemeldet.
- Player-Engine, Warteschlange und Oberfläche liegen im eigenständigen `player`-Modul.

# MusicTagStudio 0.8.4-beta

## Lyrics-Polishing und Stabilisierung

- Quellen werden als lokale LRC-Datei, eingebettete Lyrics oder lokal zwischengespeicherte LRCLIB-Daten verständlich bezeichnet.
- LRCLIB-Abrufzeiten erscheinen im lokalen Datums- und Zeitformat.
- Synchronisierte Lyrics können wahlweise als Lesetext oder mit LRC-Zeitmarken angezeigt werden.
- Eigene Statusdarstellungen unterscheiden Erfolg, laufende Abfrage, Offlinezustand, fehlende Treffer und unvollständige Metadaten.
- Nicht erreichbare Audiodateien verhindern das Einbetten, ohne lokale Lyrics aus dem Dialog zu entfernen.
- Tastenkürzel: Strg+L für LRCLIB live, Strg+S für LRC-Speicherung und Strg+E für die Einbettungsvorschau.
- Quellenwahl und Liedtext besitzen zugängliche Bezeichnungen für assistive Bedienung.

# MusicTagStudio 0.8.4-alpha3

## Bestätigtes Einbetten

- Der Lyrics-Dialog zeigt vor dem Einbetten vorhandene und neue Lyrics nebeneinander.
- Bestehende eingebettete Lyrics werden nur nach ausdrücklicher Bestätigung ersetzt.
- Andere Metadaten und vorhandene LRC-Dateien bleiben unverändert.
- MP3/ID3, FLAC, Ogg Vorbis, Opus, WavPack/APE, MP4/M4A/M4B und WMA/ASF werden unterstützt.
- ID3-, Vorbis- und APEv2-basierte Formate behalten synchronisierte Zeitmarken.
- Bei MP4 und ASF wird vorab darauf hingewiesen, dass nur Klartext eingebettet wird.
- Vor dem Schreiben wird eine temporäre Sicherheitskopie angelegt; bei Fehlern wird die Audiodatei wiederhergestellt.

# MusicTagStudio 0.8.4-alpha2

## Sichtbare Lyrics-Ansicht

- Im Tagger öffnet „Lyrics anzeigen“ für genau einen ausgewählten Titel einen eigenen Lyrics-Dialog.
- Lokale LRC-Dateien, eingebettete Varianten und lokal zwischengespeicherte LRCLIB-Texte werden sofort angeboten.
- Quelle, Synchronisationsstatus, LRCLIB-ID und Abrufzeitpunkt sind sichtbar.
- „LRCLIB prüfen“ verwendet den schonenden Cache-Endpunkt; „LRCLIB live suchen“ löst nur auf ausdrücklichen Klick eine Live-Abfrage aus.
- Netzwerkzugriffe laufen im Hintergrund und blockieren die Oberfläche nicht.
- Die ausgewählte Quelle kann als UTF-8-LRC neben der Audiodatei gespeichert werden.
- Bei möglicherweise abweichenden Live-Fassungen erscheint der vorbereitete Warnhinweis direkt über dem Liedtext.

# MusicTagStudio 0.8.4-alpha1.1

## Lyrics-Härtung vor alpha2

- LRC-Strophen und Leerzeilen bleiben beim Lesen und Schreiben erhalten.
- Mehrere Zeitmarken derselben LRC-Zeile erzeugen keinen doppelten Anzeigetext mehr.
- Instrumentalstücke werden als gültiger Lyrics-Status behandelt.
- Leere Lyrics überschreiben keine vorhandene LRC-Datei; temporäre Dateien werden bei Fehlern entfernt.
- Mehrere eingebettete Lyrics-Frames und Sprachvarianten stehen getrennt zur Auswahl bereit.
- Die Audiodauer kann direkt aus der Datei für die exakte LRCLIB-Suche ermittelt werden.
- Ein lokaler SQLite-Lyrics-Cache verhindert unnötige wiederholte Onlineabfragen.
- Einheitliche Quellenreihenfolge: lokale LRC, eingebettete Varianten, lokaler Cache, bewusste Onlineabfrage.
- Bei erkannten Live-/Concert-/Unplugged-Versionen warnt die Auflösung, wenn die Lyrics nicht ausdrücklich als Live-Version gekennzeichnet sind.

# MusicTagStudio 0.8.4-alpha1

## Lyrics-Grundlage

- Einheitliches Modell für synchronisierte und unsynchronisierte Lyrics.
- Eingebettete Lyrics werden aus ID3-, Vorbis-/FLAC-, MP4- und APE-Tags gelesen.
- LRC-Dateien werden einschließlich Metadaten, mehreren Zeitmarken und Offset gelesen.
- Lyrics können atomar als UTF-8-LRC-Datei neben der Audiodatei gespeichert werden.
- LRCLIB ist als schreibgeschützter Provider ohne API-Schlüssel angebunden.
- Standardmäßig wird der cache-schonende Endpunkt `/api/get-cached` verwendet; eine spätere UI-Aktion kann bewusst eine Live-Abfrage auslösen.

## Suche und Oberfläche

- Ab drei eingegebenen Zeichen erscheinen Künstler-Vorschläge nach einer kurzen Eingabepause.
- Die Vorschlagssuche führt begrenzte Künstlerergebnisse aus MusicBrainz und Deezer zusammen und startet noch keine Diskografie- oder Discogs-Abfrage.
- Anklicken eines Vorschlags öffnet die vollständige Künstleransicht.
- Suche und Vorschlagsliste erhielten eine ruhigere, abgerundete Darstellung nach dem Vorbild moderner Musikbibliotheken.
- Bei gleich guten Künstlernamen wird das in den Einstellungen gewählte Land bevorzugt, ohne internationale Treffer auszublenden.
- Fehlt ein Cover im Cover Art Archive, sucht die Medienbibliothek mit Discogs-Token gezielt nach Künstler, Titel und Jahr und verwendet nur einen exakten Treffer.
- MusicBrainz-Beziehungen unterscheiden jetzt Künstleridentitäten, bürgerliche Personen und bloße Namensvarianten.
- Verknüpfte eigenständige Künstler werden über ihre eindeutige MusicBrainz-ID statt über eine erneute unscharfe Namenssuche geöffnet.
- Rollen, Zeiträume und ehemalige Mitgliedschaften bleiben in der Beziehungsansicht sichtbar; verspätete Antworten eines zuvor geöffneten Künstlers werden verworfen.

# MusicTagStudio 0.8.3

Die Beta-Phase ist abgeschlossen; die Medienbibliothek mit MusicBrainz-,
Discogs-, Cache-, Status- und Navigationsfunktionen ist als stabile Version
freigegeben.

## UI-Polishing und Navigation

- Einheitliche Statusspalte in Discografie- und Tabellenansicht.
- 🟢 Lokal verfügbar
- 🟡 Externe Quelle nicht erreichbar
- ⚪ Nicht vorhanden
- Status wird ebenfalls in Coverraster, Coverliste und Detailkopf angezeigt.
- Anklickbare Breadcrumb-Navigation für Künstler, Beziehungen und Veröffentlichungen.
- Ein Pfad kann beispielsweise „Aggro Berlin › Sido › Maske“ abbilden.
- Wenn MusicBrainz keinen Künstler findet, sucht die Medienbibliothek nach exakten Discogs-Künstlern, Labels und Veröffentlichungen.
- Eigenständige Discogs-Labels wie „ersguterjunge“ können direkt geöffnet werden.
- Alte Verknüpfungen, Editionsdetails und lokale Albumaktionen werden bei einer neuen Suche zuverlässig geleert.
- Discogs-Labels zeigen automatisch die auf ihren Veröffentlichungen vertretenen Hauptkünstler.
- Pro Künstler werden Veröffentlichungsanzahl und Zeitraum angezeigt; Einträge sind anklickbar.
- Die Liste ist ausdrücklich als Discogs-Ableitung und nicht als bestätigtes Vertragsverhältnis gekennzeichnet.

## Discogs-Erweiterung

- Persönliches Discogs-API-Token kann in den Einstellungen hinterlegt werden.
- Ohne Token arbeitet die Medienbibliothek weiterhin ausschließlich mit MusicBrainz.
- Mit Token ergänzt Discogs die ausgewählte Künstlerdiskografie im Hintergrund.
- Doppelte Veröffentlichungen werden anhand von Titel und Jahr zusammengeführt.
- Labels, Formate, Badges und fehlende Cover werden aus Discogs ergänzt.
- Nur bei MusicBrainz fehlende Veröffentlichungen erscheinen als zusätzliche Discogs-Einträge.
- Discogs-Editionen und Tracklisten können direkt in der Medienbibliothek geöffnet werden.
- Discogs-Anfragen werden gedrosselt, das Token wird im Authorization-Header übertragen und HTTP 429 einmal kontrolliert wiederholt.
- Alle MusicBrainz-Zugriffe teilen sich gemäß API-Vorgabe ein anwendungsweites Limit von höchstens einem Aufruf pro Sekunde.
- MusicBrainz-User-Agents verwenden in Explorer, Tagger, Direktabgleich und Coversuche einheitlich die aktuelle Programmversion.
- Discogs-Ergänzungen erfordern nun eine exakte Künstler- oder Labelübereinstimmung; ähnlich benannte Mitwirkende werden nicht mehr fälschlich als Hauptkünstler gewählt.
- Labeldiskografien werden ohne bis zu 100 serielle Detailanfragen geladen; vollständige Release- und Trackdaten folgen erst bei Auswahl eines Eintrags.
- Discogs-Diskografien werden in einer lokalen SQLite-Datenbank zwischengespeichert und bei Folgesuchen ohne API-Anfrage sofort verwendet.
- „Discogs live aktualisieren“ umgeht den lokalen Cache bewusst und ersetzt ihn durch den aktuellen API-Stand.
- „Lokales Album im Tagger öffnen“ übergibt den erkannten Albumordner wieder korrekt an das Hauptfenster.
- Die linke Hauptnavigation ist schmaler und verwendet kompaktere Schaltflächen ohne abgeschnittene Beschriftungen.

- Neuer Bereich „Verknüpfungen“ in der Medienbibliothek.
- MusicBrainz-Beziehungen zu Künstlern, Gruppen, Mitgliedern, Labels, Aliasen und Mitwirkenden werden geladen.
- Ein Klick auf einen verknüpften Künstler öffnet dessen Suche und Diskografie.
- MusicBrainz-Aliase werden aus dem Künstlerdatensatz übernommen und sind als interne Suche anklickbar.
- Verknüpfte Labels öffnen beim Anklicken ihre eindeutige MusicBrainz-Seite.
- Tippfehler wie „Stiber Twins“ und „Aggo Berlin“ liefern den ähnlichsten Künstler zuerst, auch wenn die allgemeine Suche bereits unscharfe Treffer findet.
- Lokale Statusanzeige vereinheitlicht: „Lokal verfügbar“, „Externe Quelle nicht erreichbar“, „Nicht vorhanden“.
- Fehlerhafte Aktualisierung der lokalen Statusspalte im Discografiebaum korrigiert.

# Changelog

## Quellentransparenz in der Medienbibliothek

- Die Detailansicht weist MusicBrainz, Discogs, Apple Music und die lokale
  Bibliothek als getrennte Quellen aus.
- Bei zusammengeführten Veröffentlichungen werden nur die tatsächlich von
  Discogs ergänzten Angaben wie Labels, Formate, Kategorien oder Cover genannt.
- Das Ergebnis einer bewussten Apple-Music-Prüfung wird direkt in der
  Quellenübersicht aktualisiert.
- Die Detailspalte erhält mehr Platz; die Quellenkarte sitzt kompakt neben dem
  Cover und die Trackliste bleibt für mehrere sichtbare Titel hoch genug.
- Apple-Music-Links werden nur noch bei ausreichend sicherer Albumzuordnung
  aktiviert. Künstler, Jahr und bekannte Titelzahl fließen in die Prüfung ein;
  verspätete Ergebnisse eines zuvor ausgewählten Albums werden verworfen.
- Platzhalter wie „Unbekannter Künstler“ werden bei der Apple-Suche durch den
  aktuell ausgewählten Künstler ersetzt.
- Die Quellenkarte besitzt genug Mindesthöhe, damit auch der lokale
  Bibliotheksstatus vollständig sichtbar bleibt.
- Albumtitel mit Schrägstrichen werden bei Apple Music zusätzlich mit Leerraum-
  und Bindestrichvarianten gesucht, beispielsweise `Deja Vu 1/2` und
  `Deja Vu 1 2`.
- Die Spaltenköpfe der Discografie sortieren die Veröffentlichungen innerhalb
  ihrer jeweiligen Kategorie auf- oder absteigend.
- Liefert Apples Albumsuche keinen sicheren Treffer, wird die Collection-ID
  durch übereinstimmende Treffer mehrerer bereits geladener Albumtitel
  ermittelt; Album, Künstler und Titelzahl müssen weiterhin exakt passen.
- Exakte Künstlernamen stehen in den Live-Vorschlägen immer vor populären,
  aber nur indirekt verwandten Deezer-Treffern.
- Fehlt in der schnellen Präfixsuche ein direkter Treffer, startet die
  Vorschlagsleiste einen begrenzten Fuzzy-Fallback. Wahrscheinliche
  Schreibkorrekturen erscheinen als „Meintest du: …?“.
- Fehlende oder als unbekannt markierte Künstlerangaben einer Veröffentlichung
  werden in den Explorer-Ansichten aus dem eindeutig ausgewählten
  Künstlerkontext ergänzt.
- Beim Zusammenführen ersetzt ein strukturierter Discogs-Hauptkünstler einen
  fehlenden MusicBrainz-Künstlerwert; die Herkunft wird in der Quellenkarte
  ausgewiesen. Normalisierung mit Umlauten funktioniert dabei zuverlässig.
- Die Quellenkarte berücksichtigt mehrzeilige Discogs-Herkunftsangaben auch
  im Dark Theme vollständig.
- Lange Discogs-Herkunftslisten erscheinen kompakt mit der Zahl weiterer
  Ergänzungen; der Tooltip enthält weiterhin sämtliche Details. Reduzierte
  Abstände verhindern Überschneidungen mit der Aktionsleiste.
- Apple-Music-Prüfergebnisse gelten gemeinsam für alle Explorer-Ansichten und
  werden für spätere Programmstarts gespeichert. Die Schaltfläche zur
  bewussten erneuten Prüfung bleibt verfügbar.
- Erfolgreiche Apple-Prüfungen zeigen ihren letzten Prüfzeitpunkt und verfallen
  automatisch nach sieben Tagen. Uneindeutige Ergebnisse werden nicht über
  den aktuellen Programmstart hinaus gespeichert.
- Der bisher Apple-spezifische UI-Speicher wurde durch einen allgemeinen
  SQLite-Cache für Streaming-Verfügbarkeiten ersetzt. Anbieter, Land, Status,
  externe ID, URL, Prüfzeitpunkt und Ablaufzeit sind getrennt modelliert;
  weitere Dienste können dieselbe Infrastruktur verwenden.

## v0.8.2.2

### Medienbibliothek

- fehlende `_artist_text()`-Funktion ergänzt
- Absturz nach erfolgreicher MusicBrainz-Suche behoben
- Künstlername und vorhandene Zusatzinformationen werden in der Trefferliste angezeigt
- realistischeren UI-Regressionstest für geladene Künstler ergänzt



## v0.8.2.1

### Fehlerkorrektur

- fehlenden Handler für anklickbare Künstlervorschläge ergänzt
- Startabsturz der Medienbibliothek behoben
- Vorschlagslink übernimmt den Künstlernamen und startet die Suche erneut



## v0.8.2

### Medienbibliothek

- neuen MusicBrainzClient eingeführt
- CatalogSearchController für Künstler und Veröffentlichungen eingeführt
- dreistufige Künstlersuche mit Fuzzy-Fallback
- anklickbare Rechtschreibvorschläge
- sichtbare Diagnoseausgabe in der Medienbibliothek
- lokaler MusicBrainz-JSON-Cache
- eigenes MusicBrainz-Diagnoselog
- eindeutige Netzwerk-, HTTP- und JSON-Fehlertexte

### Roadmap

- Lyrics-Anzeige für den internen Player vorgemerkt
- optionales Schreiben von Liedtexten in unterstützte Audio-Tags vorgemerkt



## v0.8.1.2

### Tagger und Musikquellen

- hartcodierten Albumordner entfernt
- Quellenscan befüllt Bibliotheksindex und Tagger in einem Durchlauf
- mehrere Musikquellen werden im Tagger zusammengeführt
- erneutes Einlesen berücksichtigt alle aktiven erreichbaren Quellen

### Medienbibliothek

- MusicBrainz-Künstlersuche auf einfache Standardsuche umgestellt
- Fuzzy-Fallback mit MusicBrainz/Lucene-Syntax ergänzt
- anklickbare „Meintest du vielleicht …?“-Vorschläge
- eindeutige Meldungen bei null Treffern und bei Netzwerkfehlern
- Online-Timeout auf zwölf Sekunden begrenzt



## v0.8.1.1

### Fehlerkorrektur

- fehlenden `QGridLayout`-Import ergänzt
- MusicTagStudio startet wieder
- responsives Tagger-Layout bleibt erhalten



## v0.8.1

### Fehlerkorrekturen

- Musikquellen dauerhaft und unabhängig vom Startordner gespeichert
- Bibliotheksstatistik nach Tagger-Scan und beim Öffnen der Startseite aktualisiert
- MusicBrainz-Künstlersuche mit weniger strengem Fallback ergänzt

### Bedienung

- Schnellzugriff von der Startseite entfernt
- Ersteinrichtung führt ohne konfigurierte Quellen direkt zu den Einstellungen
- responsive Tagger-Aktionsleiste mit verkürzten Beschriftungen und Tooltips
- DPI-Skalierung für 100, 125, 150 und 200 Prozent vorbereitet

### Mehrsprachigkeit

- Übersetzungsgrundlage und Sprachauswahl ergänzt
- Automatisch (System), Deutsch, Englisch, Spanisch, Französisch, Italienisch,
  Portugiesisch (Portugal) und Portugiesisch (Brasilien)
- Speichern-/Abbrechen-Schaltflächen reagieren auf die Sprachauswahl



## v0.8.0.4

### Hauptfenster

- horizontale Größenänderung wieder ermöglicht
- starre Breite des rechten Metadatenbereichs entfernt
- anpassbaren Bereich zwischen Tabelle und Metadateneditor eingeführt
- sinnvolle minimale Fenstergröße gesetzt

### Navigation

- Einstellungen aus der Seitenleiste entfernt
- Einstellungen unter Datei eingeordnet
- Beenden am Ende des Datei-Menüs ergänzt

### Repository und Releases

- `.gitignore` ergänzt
- Release-Prüfung bereinigt Python- und pytest-Caches automatisch
- `.pyc` und `.pyo` werden nicht mehr mit ausgeliefert



## v0.8.0.3

### Hauptfenster

- Symbolleiste „Hauptfunktionen“ vollständig entfernt
- doppelte Navigation beseitigt
- „Ordner“ in „Ordner hinzufügen …“ umbenannt
- „Ordner hinzufügen …“ und „Neu einlesen“ unter „Datei“ eingeordnet
- Rückgängig und Wiederholen ausschließlich unter „Bearbeiten“
- Toolbar-Kontextmenü entfällt automatisch

### Tests

- Regressionstest stellt sicher, dass keine Hauptsymbolleiste mehr existiert
- Menütests für Datei und Bearbeiten ergänzt



## v0.8.0.2

### Medienbibliothek

- verwaistes Veröffentlichungsfilter-Feld entfernt
- fehlerhafte Signalverbindung zu nicht mehr vorhandener Methode entfernt
- Startabsturz der Medienbibliothek behoben

### Tests

- veralteten Discogs-UI-Test entfernt
- veralteten Test der globalen Suchmodi entfernt
- Regressionstest für die bewusst vereinfachte Suche ergänzt



## v0.8.0.1

### Hellmodus

- neue weiß-blaugraue Farbpalette
- blauer, zurückhaltender Akzent
- Navigation und Toolbar optisch beruhigt
- Tabellen, Eingabefelder und Auswahlflächen überarbeitet
- Kontraste und Lesbarkeit verbessert
- keine Änderungen am Aufbau der Benutzeroberfläche



## v0.8.0

### Design

- Light Theme vollständig neu gestaltet
- Dark Theme vereinheitlicht
- moderne Buttons, Eingabefelder, Tabellen und Scrollleisten
- konsistente Akzentfarbe
- überarbeitete Tooltips und Menüflächen

### Startseite

- neues Dashboard als Startansicht
- Kennzahlen für Alben, Künstler, Titel und Quellen
- Online-/Offline-Status der Musikquellen
- Schnellzugriff auf alle Arbeitsbereiche
- manueller Index-Refresh

### Toolbar und Statusleiste

- neue Hauptsymbolleiste
- Ordner öffnen, Scan, Undo/Redo und Workspace-Wechsel
- Statusmeldungen statt blockierender Speicherbestätigung



## v0.7.5.1

### Suche vereinfacht

- Discogs vorerst vollständig aus der sichtbaren Medienbibliothek entfernt
- Discogs-Token-Feld aus den Einstellungen entfernt
- Suchmodus-Drop-down entfernt
- ein einziges Suchfeld startet wieder die stabile MusicBrainz-Künstlersuche
- irreführende globale Suche und Token-Meldung entfernt
- Tabellen-, Cover- und Discografieansichten bleiben erhalten



## v0.7.5.0

- Discografie, Tabelle, Coverraster und Cover + Liste
- vier Covergrößen
- Ansicht und Covergröße gespeichert
- Filter auf alle Ansichten erweitert



## v0.7.4.0

### Globale Medienbibliotheks-Suche

- Suchmodi Alles, Künstler, Veröffentlichung und Label
- gemischte Trefferliste mit Künstlern, Releases, Mastern und Labels
- direkte Release- und Master-Suche
- Labelsuche samt Label-Veröffentlichungen
- Discogs-Künstler direkt als Katalogeinstieg
- Suchbegriffe wie Aggro Ansage, ersguterjunge oder Death Row Records
- direkte Einordnung der Treffer in die MusicTagStudio-Kategorien



## v0.7.3.2

### Kritischer GUI-Startfehler

- fehlenden `Qt`-Import in `library_audit_dialog.py` ergänzt
- Absturz bei `Qt.WindowType.Widget` behoben
- vollständigen Headless-GUI-Starttest ergänzt
- automatischen Wechsel durch alle Workspaces im Test ergänzt



## v0.7.3.1

### Kritischer Startfehler

- zyklischen Import zwischen Einstellungen, Musikquellen und Proposal-Service
  behoben
- Scanner-Import in `library_sources.scan_source()` verzögert
- Importtest für Einstellungen und Medienbibliothek ergänzt



## v0.7.3.0

### Medienbibliothek 2.0

- eigene Sammler-Kategorien
- Mixtape-, Soundtrack-, Boxset- und Bootleg-Erkennung
- Sampler: mehrere Künstler, ein gemeinsames Label
- Compilation: mehrere Künstler, mehrere Labels
- neue SVG-Icons für die zusätzlichen Kategorien
- Filter innerhalb der Künstlerveröffentlichungen

### Discogs

- optionaler persönlicher Token in den Einstellungen
- manuelle Künstler- und Veröffentlichungsabfrage
- Discogs-exklusive Releases ergänzen
- Discogs-Tracklisten und Edition-Cover
- Formate, Labels und Badges
- keine automatische Discogs-Abfrage



## v0.7.2.3

### Musikquellen

- beliebig viele lokale, externe und Netzwerk-Musikquellen
- Quellenverwaltung in den Einstellungen
- Aktiv-/Deaktiv-Schalter, Name, Pfad und Erreichbarkeitsstatus
- automatische Quellenladung beim Programmstart
- optionaler Hintergrundscan beim Programmstart
- genaue Warnung bei nicht gefundenen Pfaden

### Bibliotheksindex

- persistenter lokaler Albumindex
- offline befindliche Quellen bleiben sichtbar
- erreichbare Quellen werden beim Scan aktualisiert
- Offline-Alben können nicht im Tagger geöffnet werden
- „Mehr vom Künstler“ und Online-Discografie bleiben unabhängig nutzbar



## v0.7.2.2

### Workspaces

- Audio-Analyse vollständig in das Hauptfenster eingebettet
- Bibliotheksprüfung vollständig in das Hauptfenster eingebettet
- Einstellungen vollständig in das Hauptfenster eingebettet
- unnötige Öffnen-Schaltflächen und Zwischenansichten entfernt
- markierte und gescannte Titel werden beim Wechsel aktualisiert
- Einstellungen lassen sich direkt im Workspace speichern



## v0.7.2.1

### Medienbibliothek

- Kategoriebaum im Explorer-Stil überarbeitet
- SVG-Icons für Album, Live, EP, Single, Compilation und weitere Typen
- Aufklapppfeil direkt an der Kategorieüberschrift
- Anzahl der Veröffentlichungen pro Kategorie
- Covervorschau der konkreten Edition
- lokales Cover vor Cover Art Archive bevorzugt
- persistenter Cover-Cache
- Schutz vor veralteten Cover-Rückmeldungen

### Navigation

- doppelte Menüs in der oberen Menüleiste entfernt
- „Mehr vom Künstler“ im Tagger ergänzt
- automatischer Wechsel und Suche in der Medienbibliothek



## v0.7.2

### Oberfläche

- feste Workspace-Navigation
- direkte Bereiche für Tagger, Medienbibliothek, Audio-Analyse,
  Bibliotheksprüfung und Einstellungen

### Medienbibliothek

- MusicBrainz-Künstlersuche
- Discografie als Release-Gruppen
- Editionen mit Datum, Land, Status, Format, Medien- und Trackzahl
- Tracklisten mit Disc- und Tracknummern
- manueller Apple-Music-Verfügbarkeitscheck
- lokaler Abgleich mit dem aktuellen Scan
- lokales Album im Tagger öffnen
- Qualitätsabfragen nur auf Knopfdruck

### Audioformate

- Monkey's Audio (`.ape`)
- WMA/ASF (`.wma`, `.asf`)
- M4B (`.m4b`)

### BBCode

- Künstlerordner anhand des Albumkünstlernamens robust ermittelt



## v0.7.1.6

### Coverdialog

- Möglichen nativen Absturz durch späte QRunnable-Rückrufe behoben
- Globalen Thread-Pool durch dialogeigenen Pool ersetzt
- Aktive Worker werden bis zu ihrem Abschluss referenziert
- Closure-basierte Widget-Rückrufe durch gebundene Qt-Slots ersetzt
- Ergebnisse nach dem Schließen werden verworfen
- Vorschau-Prefetch auf den gewählten und zwei weitere Treffer begrenzt
- Diagnoseprotokoll `logs/cover.log` ergänzt



## v0.7.1.5

### BBCode-Text

- Tracklisten nach CDs gruppiert
- CD-Überschriften im Format `[b]CD1[/b]:`
- Originale Apple-Music-Tracktitel werden für die Ausgabe geladen
- Lokale, normalisierte Artist-Tags bleiben unverändert
- Sicherer Fallback auf lokale Titel
- Links-Platzhalter ohne zusätzlichen Image-BBCode

### Haupttabelle

- Track- und Discnummern zweistellig formatiert
- Beispiele: `01/27`, `02/27`, `01/02`



## v0.7.1.4

### Auswahl und Editor

- Falsche Warnung zu ungespeicherten Änderungen behoben
- `comment` zu `EDITABLE_FIELDS` ergänzt
- Feldbezeichnung „Kommentar“ zentral ergänzt
- Ausgangswerte und aktuelle Editorwerte besitzen wieder dieselben Felder
- Titelwechsel, Mehrfachauswahl und Strg+A lösen ohne echte Änderung keine
  Speicherabfrage mehr aus



## v0.7.1.3

### Kritischer Startfehler

- `comment` war in `OPTIONAL_FIELDS`, aber nicht in `table_fields` enthalten
- dadurch scheiterte `update_optional_columns()` beim Programmstart
- Kommentarspalte vollständig ergänzt
- GUI-Smoke-Test für die Erzeugung des Hauptfensters hinzugefügt



## v0.7.1.2

### Hauptfenster

- COMMENT-Feld als „Kommentar“ ergänzt
- Editorbereich scrollbar gemacht
- Alle Tabellenspalten frei veränderbar
- Spaltenbreiten über QSettings dauerhaft gespeichert
- Menüpunkt zum Zurücksetzen ergänzt

### Audioanalyse

- Absturz in closeEvent behoben
- Bereits gelöschte Qt-Threadobjekte werden sicher erkannt
- Threadreferenz wird nach finished auf None gesetzt
- Schließen und Abbrechen gegen RuntimeError abgesichert



## v0.7.1.1

### BBCode-Textvorlage

- Fehlerhafte Aktivierungslogik des Buttons korrigiert
- Status wird unmittelbar nach dem Scan aktualisiert
- Status wird bei jeder Auswahländerung aktualisiert
- Funktioniert bei Einzelwahl, Mehrfachwahl und Strg+A
- Mehrere Alben in einer Auswahl werden zuverlässig erkannt
- Aussagekräftige Tooltips bei deaktiviertem Button
- Beschriftung in „BBCode-Text erstellen“ geändert



## v0.7.1

### Coverdialog

- Vorschaubilder werden nach der Suche parallel vorgeladen
- Gemeinsamer RAM-Cache für Vorschaubilder
- Keine doppelten Downloads derselben Vorschau
- Kürzeres Vorschau-Zeitlimit ohne Einfluss auf den Originaldownload

### Metadaten

- Kommentarfeld im Haupteditor ergänzt

### Textvorlage

- Manueller Button zur Erstellung einer BBCode-Textdatei
- Ausgabe im Ordner des 400-px-Covers
- Automatische Tracklist
- Format aus den ausgewählten Audiodateien
- Technische Qualitätsangaben über ffprobe im Hintergrund
- Größe bleibt zur manuellen Ergänzung leer



## v0.7.0

### Workflow

- Automatischer Scan nach Ordnerauswahl
- Scan-Button in „Bibliothek neu einlesen“ umbenannt
- Feldgenaue Änderungsvorschau vor dem Schreiben

### Undo, Redo und Sicherheit

- Rückgängig über Strg+Z und Button
- Wiederholen über Strg+Y/Standard-Redo und Button
- Vollständige Dateisicherungen vor Schreiboperationen
- Undo/Redo für Einzel- und Batch-Tags, direkte Albumabfragen und Cover
- Sitzungsbasierter Änderungsverlauf
- Persistente Manifeste unter `.musictagstudio/history/`

### Internes Testsystem

- Reale Regressionstests für Clueso, Stieber Twins und Remaster-Titel
- Zentrale Release-Prüfung über `scripts/release_check.py`
- GitHub-Actions-Workflow für jeden Push und Pull Request
- Neue Tests für Undo und Redo



## v0.6.8.7

- Alternative Apple-Albumtitel-Suchvarianten
- Collection-ID-Recovery aus bis zu acht markanten Songtreffern
- Mehrheitsentscheidung und Lookup-Validierung
- Prüfung von Albumname und Trackzahl
- Normalisierung vollständiger Datumswerte auf das Jahr
- Ausführliche Recovery-Protokolle



## v0.6.8.6

### Diagnose ab Programmstart

- Protokollierung beginnt vor `QApplication`
- Eindeutige Sitzungs-ID pro Programmstart
- Python-, Betriebssystem-, Pfad- und Prozesseinträge
- Geladene Einstellungen und verwendete Metadatenquelle
- Globale Protokollierung unbehandelter Ausnahmen und Thread-Ausnahmen
- Qt-Meldungen in `logs/qt.log`
- Stabiler Projektordner für Logs und Cache statt abhängigem Arbeitsordner

### Vollständiger Metadaten-Ablauf

- Lokale Eingabedaten jedes markierten Titels
- Bildung der Albumgruppen und ermittelte Albumidentität
- Jede Apple-Albumsuchanfrage
- Alle Albumkandidaten samt Score
- Entscheidung am Mindestscore
- Lookup-Aufrufe und Lookup-Fehler
- Globale Matching-Ergebnisse
- Fehlende lokale Titel
- Exakte Track-Nachsuche und Search-Fallback
- Endergebnis und Warnungen pro Titel



## v0.6.8.5

### Vollständige Apple-Lookup-Diagnose

- Unveränderte Apple-Antworten werden als JSON gespeichert
- Separate Dateien pro Collection-ID und Store
- Jeder Antwort-Eintrag wird protokolliert
- Auch verworfene Einträge erscheinen im Log
- Verwerfungsgründe werden einzeln genannt
- Zusammenfassung über akzeptierte und verworfene Einträge
- Diagnosepfade: `logs/apple_music.log` und `cache/apple/`



## v0.6.8.4

### Apple-Music-Lookup verbessert

- Fehlende Albumtracks werden zuerst per Lookup-API nachgeladen
- Eingestellter Store und US-Store werden geprüft
- Exakter Abgleich nach Collection-ID, Discnummer und Tracknummer
- Search-API nur als letzter streng gefilterter Rückfall
- `limit=200` für Apple-Album-Lookups
- Vollständiges Trackprotokoll in `logs/apple_music.log`

### Versionsnamen normalisiert

- `remastered` entspricht `remaster`
- `remixed` entspricht `remix`



## v0.6.8.3

### WavPack-Cover korrigiert

- Cover werden direkt aus APEv2 gelesen
- `Cover Art (Front)` wird fallunabhängig erkannt
- APEv2-Binärformat mit Dateiname und Null-Trennzeichen wird korrekt zerlegt
- Kein WavPack-Audiostream-Parsing mehr für Cover
- Fehlerhafte doppelte WavPack-Verzweigung in `embed_cover()` entfernt
- WavPack-Cover können korrekt ersetzt und eingebettet werden
- Fehlerdetails werden in `logs/wavpack.log` protokolliert



## v0.6.8.2

### WavPack-Leser weiter abgesichert

- Dreistufiges Lesen über APEv2, Mutagen WavPack und ffprobe
- ffprobe-Tags werden in das gemeinsame Song-Modell übertragen
- DXD-WavPack-Dateien können auch bei einem Mutagen-Parserfehler gescannt werden
- Schreibfehler werden nicht mehr verschluckt
- Vollständige Tracebacks in `logs/wavpack.log`
- Scanner protokolliert jede übersprungene Datei in `logs/scanner.log`
- Scanmeldung verweist auf die technischen Logdateien



## v0.6.8.1

### WavPack-Scan robust gemacht

- Direkter APEv2-Zugriff für `.wv`
- Kein vollständiges Parsen des WavPack-Audiostreams zum Taglesen nötig
- Unterstützung ungewöhnlicher DXD-WavPack-Dateien verbessert
- Detaillierter Scanbericht mit übersprungenen Dateien und Fehlerursachen

### Exakte Apple-Song-Links

- Apple-Song-URLs werden von Album-URLs unterschieden
- Offizieller ID-Lookup für einen einzelnen Apple-Music-Song
- Exakte Song-ID kann einer einzelnen markierten Datei zugeordnet werden



## v0.6.8.0

### Metadatenquellen entkoppelt

- Apple Music und MusicBrainz werden unabhängig voneinander abgefragt
- Bevorzugte Quelle beeinflusst nur noch die Vorauswahl
- Eigenes SourceProposal-Modell pro Anbieter
- Quellenstatus und Kandidaten werden getrennt gespeichert
- Ein fehlender Treffer einer Quelle unterdrückt keine andere Quelle

### WavPack vollständig unterstützt

- `.wv` in der zentralen Liste unterstützter Audioformate
- APEv2-Metadaten lesen und schreiben
- Cover Art (Front) lesen und einbetten
- ReplayGain in APEv2 schreiben
- Bibliotheksprüfung nutzt den zentralen Cover-Leser
- Audioanalyse funktioniert über FFmpeg/ffprobe
- FLAC-spezifische Formulierung im Batchdialog entfernt



## v0.6.7.8

### MusicBrainz-Fallback korrigiert

- Nur erfolgreich zugeordnete Release-Tracks werden als aufgelöst markiert
- Nicht zugeordnete Titel erhalten anschließend die titelweise MusicBrainz-Suche
- Teilweise passende Releases blockieren nicht mehr die restlichen Titel
- Zusätzlicher Hinweis bei nicht eindeutiger Release-Zuordnung



## v0.6.7.7

### Unvollständige Apple-Albumtracklisten abgesichert

- Strenge Nachsuche fehlender Tracks innerhalb einer bekannten collectionId
- Abgleich von collectionId, Discnummer und Tracknummer
- Storeübergreifende Nachsuche im konfigurierten Store und im US-Store
- Kein allgemeiner Song-Fallback mehr, sobald das Album sicher erkannt wurde
- Falsche Ersatztreffer wie „Jedes Jahr“ für „Minimum“ werden dadurch ausgeschlossen
- Apple-Song-IDs werden aus Album-Lookups übernommen
- Aussagekräftige Warnung, falls ein Track auch albumgebunden nicht auffindbar ist



## v0.6.7.6

### Albumtracklisten für Apple Music und MusicBrainz stabilisiert

- Apple-Tracklisten mehrerer Stores werden nach tatsächlicher Zuordnungsabdeckung verglichen
- Vollständigste passende Apple-Trackliste wird verwendet
- Kein Einzeltrack-Fallback nach erfolgreich erkannter Albumquelle
- MusicBrainz-Release-Suche und vollständige Release-Trackliste im Batch
- Globale MusicBrainz-Zuordnung statt exakter Einzelaufnahme-Suche
- MusicBrainz-Anfragen der direkten Release-Abfrage werden rate-limitiert
- Fehlende Quellwerte entstehen nur noch bei wirklich nicht sicher zuordenbaren Titeln



## v0.6.7.5

### Apple-Music-Batchzuordnung korrigiert

- Offizielle Apple-Albumsuche für Batch-Vorschläge
- Vollständige Trackliste wird über die offizielle Lookup-API geladen
- Globale Zuordnung aller ausgewählten Dateien zur Albumtrackliste
- Unabhängige, fehleranfällige Einzeltrack-Suche dient nur noch als Rückfalllösung
- Unsichere Apple-Treffer werden nicht automatisch übernommen
- Transparenter US-Store-Fallback, falls der konfigurierte Store keinen sicheren Albumtreffer liefert
- `<leer>` aus der Mischwertanzeige entfernt
- Fehlende Werte werden verständlich als `fehlt bei … Titel(n)` angezeigt



## v0.6.7.4

### Apple-Music-Trefferauswahl und Quellenanzeige korrigiert

- Apple-Music-Suche berücksichtigt lokale Track- und Discnummer
- Dateinamentitel wird als zusätzliches Signal verwendet
- Audiodauer wird bei vorhandener Datei in die Bewertung einbezogen
- Versionszusätze wie Remix und Instrumental werden stärker gewichtet
- Normale Albumfassung wird bei gewünschtem Remix deutlich abgewertet
- MusicBrainz-Mischwerte zeigen die konkreten Werte samt Häufigkeit
- Gemischte Werte bleiben für albumweite Schreibvorgänge gesperrt



## v0.6.7.3

### Albumzuordnung vollständig neu aufgebaut

- Globale Eins-zu-eins-Zuordnung über eine Bewertungsmatrix
- Ungarischer Algorithmus bestimmt die insgesamt beste Zuordnung
- Dateinamen werden zusätzlich zu vorhandenen Tags ausgewertet
- Dreistellige Präfixe wie 109 werden als Disc 1 / Track 09 interpretiert
- Lokale Titel, Dateinamentitel, Dauer und Reihenfolge fließen in die Bewertung ein
- Falsche lokale Tracktags besitzen nur noch geringe Priorität
- Zuordnungsmatrix ist vor dem Schreiben sichtbar
- Jede Zuordnung kann manuell korrigiert werden
- Doppelte und fehlende Zuordnungen blockieren den Metadatenvergleich
- Sicherheit und Begründung werden pro Datei angezeigt



## v0.6.7.2

### Korrektur der direkten Albumzuordnung

- Eindeutige Titelübereinstimmungen haben Vorrang vor lokalen Tracknummern
- Falsch vorhandene Tracknummern blockieren nicht mehr die korrekte Zuordnung
- Disc- und Tracknummer werden als zweite Zuordnungsstufe verwendet
- Leichte Schreibvarianten werden als zusätzliche dritte Stufe berücksichtigt
- Remix- und Instrumentalzusätze werden nicht entfernt



## v0.6.7.1

### Korrektur der Tracknummernprüfung

- Tracknummern werden jetzt pro Disc geprüft
- Gleiche Tracknummern auf unterschiedlichen Discs sind zulässig
- Doppelte Tracknummern werden einzeln gemeldet
- Betroffene Dateien erscheinen vollständig in der Detailansicht
- Lücken in der Nummerierung werden pro Disc ermittelt
- Track-Gesamtzahlen werden pro Disc verglichen



## v0.6.7

### Bibliotheksprüfung Teil 1

- Neuer Hauptmenüpunkt „Bibliotheksprüfung“
- Prüfung markierter oder aller gescannten Titel
- Erkennung doppelter ISRCs
- Prüfung einheitlicher Albumwerte
- Prüfung von Tracknummern, Discnummern und Gesamtzahlen
- Erkennung fehlender und unterschiedlicher eingebetteter Cover
- Erkennung fehlender ReplayGain-Tags
- Filter nach Fehlern, Warnungen und Informationen
- Detailansicht pro Hinweis
- Erster bibliotheksweiter Gesundheitswert



## v0.6.6

### Coververwaltung verbessert

- Einheitliche Qualitätsbewertung für Cover
- MD5-Hash wird für vollständig geladene Cover berechnet
- Vergleich mit vorhandenem Master-Cover
- Unterscheidung zwischen identischem Inhalt, gleicher Auflösung und abweichendem Bild
- Beste Coverquelle wird automatisch empfohlen
- Mehralbum-Batchverarbeitung
- Vorhandene Master-Cover werden wiederverwendet
- Fehlende Master-Cover werden automatisch gesucht
- Fehler pro Album werden getrennt protokolliert



## v0.6.5

### Audioanalyse verfeinert

- True Peak bis einschließlich 1 dBTP gilt als unauffällig
- Werte über 1 bis 2 dBTP werden als erhöht markiert
- Werte über 2 dBTP werden als kritisch markiert
- Gesundheitswert gewichtet leicht erhöhte Peaks deutlich zurückhaltender
- Statistik zeigt Cache-Treffer, neu berechnete Titel, Gesamtdauer und Durchschnittszeit
- Analyseverlauf wurde lesbarer gestaltet
- Fortschrittsdialog beim Schreiben von ReplayGain-Tags
- Anzahl paralleler Analysen ist unter Einstellungen → Audioanalyse wählbar
- Analyse-Cache wurde wegen der neuen Peak-Einordnung versioniert



## v0.6.4

### Neu und verbessert

- Bis zu vier parallele FFmpeg-Analysen
- Dauerhafter Analyse-Cache unter dem lokalen Benutzerprofil
- Unveränderte Dateien werden bei späteren Durchläufen aus dem Cache geladen
- Cache kann über „Analyse-Cache ignorieren“ bewusst umgangen werden
- True-Peak-Einordnung: unauffällig, erhöht, über 0 dBTP und kritisch
- Nur die True-Peak- und Hinweiszellen werden farblich markiert
- Albumvergleich zeigt durchschnittliche Bitrate und durchschnittliche LUFS
- Album Gain und Album Peak werden angezeigt
- Erster Album-Gesundheitswert von 0 bis 100
- Analyseverlauf mit Angaben zu Cache-Treffern, neuen Analysen und Fehlern
- Album-ReplayGain wird ebenfalls im Analyse-Cache gespeichert



## v0.6.3

### Neu

- Neuer Hauptmenüpunkt „Audio-Analyse“ neben „Einstellungen“
- Automatische Erkennung von ffmpeg und ffprobe
- Technische Analyse von Codec, Container, Abtastrate, Bittiefe, Kanälen, Bitrate und Dauer
- Lautheitsanalyse mit LUFS, Loudness Range und True Peak
- Vorsichtiger Clipping-Hinweis bei True Peak nahe oder über 0 dBTP
- ReplayGain Track Gain und Track Peak
- Optionales gemeinsames Album-ReplayGain
- Albumvergleich mit Erkennung technischer Ausreißer
- Fortschrittsanzeige und Abbruchmöglichkeit
- ReplayGain-Tags für FLAC, MP3, Ogg Vorbis, Opus und M4A/MP4
- Vorhandene ReplayGain-Tags werden nur nach Bestätigung überschrieben



## v0.6.2

### Neu

- Dauerhafter Cover-Suchcache im lokalen Benutzerverzeichnis
- Suchergebnisse bleiben auch nach einem Programmneustart verfügbar
- Cache speichert nur URLs, IDs und Bildmetadaten, keine Bilder oder Zugangsdaten
- Zwischengespeicherte Ergebnisse verfallen standardmäßig nach 30 Tagen
- Schaltfläche „Online neu suchen“ um den Cache bewusst zu umgehen
- Erweiterte Qualitätsanzeige für Cover
- Anzeige von Quelle, Auflösung, Format, Dateigröße, Seitenverhältnis und Bewertung
- Vorschauauflösung und Vorschaugröße werden nach dem Laden angezeigt



## v0.6.1

### Neu

- Cover-Dialog öffnet sich sofort und lädt Ergebnisse im Hintergrund
- Apple Music und Cover Art Archive werden parallel abgefragt
- Kleine Vorschaubilder werden erst bei Auswahl geladen
- Originalcover wird erst beim endgültigen Übernehmen heruntergeladen
- Vorhandenes Master-Cover wird ohne Onlineabfrage sofort angeboten
- Suchergebnisse werden während der Programmsitzung zwischengespeichert
- Direkte Apple-Music-Albumlinks und Album-IDs werden unterstützt
- Direkte MusicBrainz-Release-Links, Release-Group-Links und MBIDs werden unterstützt
- Lokale Titel werden anhand von Disc-, Tracknummer und Titel zugeordnet
- Direkte Albumdaten werden vor dem Speichern in der Batch-Vergleichsansicht geprüft



## 0.6.0

- Coverquellen mit Ampelstatus, Tooltips und dauerhafter Auswahl
- Apple Music und Cover Art Archive als offizielle Coverquellen
- Master-Cover in bestmöglicher Qualität im Albumordner
- 1000-px-JPEG mit Qualität 100 für eingebettete Cover
- 400-px-JPEG mit Qualität 80 im konfigurierbaren übergeordneten Künstlerordner
- Cover-Einbettung für FLAC, MP3, Ogg Vorbis, Opus und M4A/MP4
- Allgemeiner Audioscan statt ausschließlich FLAC
- Mehrfachauswahl zeigt Gesamttracks bei vollständiger Albumauswahl korrekt
- Auswahlstatus zeigt Titel- und Albumanzahl
- Editorbereich besitzt eine feste Breite und wächst nicht mehr mit Feldinhalten



## 0.5.0

- Feldgenaue Quellenwahl auch in der Batch-Vergleichsansicht
- Getrennte Tabs für gemeinsame Albumwerte und individuelle Trackwerte
- Bevorzugte Quelle wird als Standardempfehlung verwendet
- Fehlende Werte können automatisch aus der anderen unterstützten Quelle ergänzt werden
- Konflikte zwischen Apple Music und MusicBrainz werden sichtbar markiert
- Gemeinsame Albumwerte können auf alle markierten Titel angewendet werden
- Tracktitel, Künstler, Tracknummer, Discnummer, ISRC und Komponist bleiben individuell auswählbar
- Nur tatsächlich ausgewählte Änderungen werden gespeichert


## 0.4.1

- Vergleichsansicht zeigt Lokal, Apple Music und MusicBrainz nebeneinander
- Bevorzugte Quelle wird deutlich hervorgehoben
- Ergänzte Felder werden gesondert gekennzeichnet
- Konflikte zwischen Anbietern werden sichtbar markiert
- Quelle kann für jedes Feld einzeln ausgewählt werden
- Nur die tatsächlich ausgewählten Fremdwerte werden in den Editor übernommen


## 0.4.0

- Neues Einstellungsfenster
- Theme-Auswahl: Automatisch, Hell oder Dunkel
- Automatischer Modus orientiert sich an der Windows-Darstellung
- Metadatenquellen mit Statusfarben und erklärenden Tooltips
- Nicht unterstützte Anbieter bleiben sichtbar, aber nicht auswählbar
- Bevorzugte Quelle wird dauerhaft in config.toml gespeichert
- Optionales Ergänzen fehlender Felder durch andere unterstützte Quellen
- Gewählte Quelle besitzt für sämtliche vorhandenen Felder Priorität
- Feature-Behandlung ist über das Einstellungsfenster auswählbar


## 0.3.2

- Gemeinsames Cover bleibt bei Mehrfachauswahl sichtbar
- Coververgleich über Bild-MD5 und technische Eigenschaften
- „Unterschiedliche Cover“ nur bei tatsächlichen Abweichungen
- Mischung aus Dateien mit und ohne Cover wird als Unterschied erkannt


## 0.3.1

- Mehrfachbearbeitung für manuell geänderte Felder
- Gemeinsame Werte werden angezeigt, unterschiedliche Werte als Platzhalter
- Nur tatsächlich bearbeitete Felder werden auf alle markierten Titel angewendet
- Konfigurierbare Feature-Behandlung: artist_only, title_and_artist oder source
- Einzelvergleich übernimmt ausgewählte Vorschläge zuverlässig in den Editor


## 0.3.0

- Regel-Engine für Feature-Künstler, Apostrophe, Genres und Künstlerlisten
- Zusammenführungsschicht mit feldbezogener Quellenpriorität
- MusicBrainz-Provider mit Rate-Limit und aussagekräftigem User-Agent
- Vergleichsansicht „Aktuell ↔ Vorschlag ↔ Quelle“
- Batch-Verarbeitung für markierte Titel
- Neue modulare Struktur mit `core`, `models`, `providers`, `services` und `ui`
- Kompatibilitätsmodule für bisherige Imports
