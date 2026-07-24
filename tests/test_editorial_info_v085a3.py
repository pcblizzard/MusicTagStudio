from musictagstudio.providers import theaudiodb
from musictagstudio.providers import apple_editorial
from musictagstudio.providers import apple_artist


def test_german_artist_biography_is_preferred(monkeypatch):
    monkeypatch.setattr(
        theaudiodb,
        "_get_json",
        lambda *_args, **_kwargs: {
            "artists": [{
                "idArtist": "1",
                "strArtist": "Clueso",
                "strBiographyDE": "Deutsche Biografie",
                "strBiographyEN": "English biography",
            }]
        },
    )

    info = theaudiodb.fetch_artist_info("Clueso", "de")

    assert info is not None
    assert info.text == "Deutsche Biografie"
    assert info.language == "de"


def test_missing_german_album_text_falls_back_to_english(monkeypatch):
    monkeypatch.setattr(
        theaudiodb,
        "_get_json",
        lambda *_args, **_kwargs: {
            "album": [{
                "idAlbum": "2",
                "strArtist": "Clueso",
                "strAlbum": "Deja Vu 1/2",
                "strDescriptionDE": "",
                "strDescriptionEN": "English album information",
            }]
        },
    )

    info = theaudiodb.fetch_album_info("Clueso", "Deja Vu 1/2", "de")

    assert info is not None
    assert info.text == "English album information"
    assert info.language == "en"


def test_english_app_language_requests_english(monkeypatch):
    monkeypatch.setattr(
        theaudiodb,
        "_get_json",
        lambda *_args, **_kwargs: {
            "artists": [{
                "strArtist": "Clueso",
                "strBiographyDE": "Deutsch",
                "strBiographyEN": "English",
            }]
        },
    )

    assert theaudiodb.fetch_artist_info("Clueso", "en").text == "English"


def test_apple_album_description_is_read_from_structured_html():
    page = """
    <div class="description" data-testid="description">
      <div><p data-testid="truncate-text">
        Der Albumtext <b>mit Formatierung</b> und &amp; Zeichen.
      </p></div>
    </div>
    """

    assert apple_editorial._html_description(page) == (
        "Der Albumtext mit Formatierung und & Zeichen."
    )


def test_apple_description_supports_short_tagline_and_multiple_paragraphs():
    short = """<div data-testid="description"><p data-testid="truncate-text">
    Es ist Zeit, Abschied zu nehmen.</p></div>"""
    long = """<div data-testid="description"><div>
    <p data-testid="truncate-text">Erster Absatz.<br>Zweiter Absatz.</p>
    </div></div>"""

    assert apple_editorial._html_description(short) == (
        "Es ist Zeit, Abschied zu nehmen."
    )
    assert apple_editorial._html_description(long) == (
        "Erster Absatz. Zweiter Absatz."
    )


def test_selected_song_parameter_is_removed_from_album_url():
    source, localized = apple_editorial._canonical_album_urls(
        "https://music.apple.com/de/album/trink-aus/1884031124?i=1884031221",
        "de",
    )

    assert source == "https://music.apple.com/de/album/trink-aus/1884031124"
    assert localized == (
        "https://music.apple.com/de/album/trink-aus/1884031124?l=de-DE"
    )


def test_apple_editorial_marker_is_a_structure_independent_fallback():
    page = """
    <section class="future-apple-layout">
      <!-- HTML_TAG_START -->
      Der Titel klingt nach Nostalgie&nbsp;– und bleibt in Bewegung.
      <!-- HTML_TAG_END -->
    </section>
    """

    assert apple_editorial._marker_description(page) == (
        "Der Titel klingt nach Nostalgie – und bleibt in Bewegung."
    )


def test_real_apple_artist_hero_background_is_accepted():
    image = (
        "https://is1-ssl.mzstatic.com/image/thumb/AMCArtistImages211/v4/"
        "artist/2400x933vf-60.webp"
    )
    page = f'<div style="--background-image: url({image});"></div>'

    assert apple_artist.extract_artist_hero_url(page) == image


def test_video_preview_is_not_used_as_artist_artwork():
    image = (
        "https://is1-ssl.mzstatic.com/image/thumb/Video115/v4/preview/"
        "PreviewImage_preview_image_nonvideo/1200x675mv.webp"
    )
    page = f'<div style="--background-image: url({image});"></div>'

    assert apple_artist.extract_artist_hero_url(page) == ""


def test_discogs_artist_image_is_used_when_apple_has_no_hero(monkeypatch, tmp_path):
    from musictagstudio.media_library import discogs

    monkeypatch.setattr(apple_artist, "_search_artist_url", lambda *_args: "")
    monkeypatch.setattr(
        discogs,
        "fetch_artist_image",
        lambda *_args: (
            "https://i.discogs.com/example/artist.jpeg",
            "https://www.discogs.com/artist/60650",
        ),
    )
    monkeypatch.setattr(
        apple_artist,
        "_download_image",
        lambda *_args: b"discogs-image",
    )

    result = apple_artist.fetch_artist_artwork(
        "Clueso", "DE", "de", tmp_path, "token"
    )

    assert result is not None
    assert result.source == "Discogs"
    assert result.data == b"discogs-image"


def test_discogs_fallback_rejects_untrusted_image_host():
    assert not apple_artist._is_discogs_image_url(
        "https://example.com/copied-discogs-image.jpg"
    )


def test_album_info_uses_confirmed_apple_url_as_fallback(monkeypatch):
    monkeypatch.setattr(
        theaudiodb,
        "fetch_album_info",
        lambda *_args, **_kwargs: None,
    )
    expected = theaudiodb.EditorialInfo(
        text="Apple album information",
        source="Apple Music",
    )
    monkeypatch.setattr(
        apple_editorial,
        "fetch_apple_editorial",
        lambda *_args, **_kwargs: expected,
    )

    result = theaudiodb.fetch_album_info_with_apple_fallback(
        "Clueso",
        "Deja Vu 1/2",
        "de",
        "https://music.apple.com/de/album/id1859696286",
    )

    assert result == expected
