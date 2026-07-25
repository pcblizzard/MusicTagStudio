from __future__ import annotations

from musictagstudio.providers import apple_editorial as ae


_LD_JSON = (
    '{"@context":"http://schema.org","@type":"MusicAlbum",'
    '"name":"Keine Angst","description":"Saubere Beschreibung."}'
)


def test_marker_description_skips_embedded_json_ld():
    # Apple bettet das JSON-LD-Script innerhalb der Editorial-Marker ein.
    page = (
        "<!-- HTML_TAG_START -->"
        f'<script type="application/ld+json">{_LD_JSON}</script>'
        "<!-- HTML_TAG_END -->"
    )
    assert ae._marker_description(page) == ""


def test_marker_description_keeps_real_prose():
    page = (
        "<!-- HTML_TAG_START -->"
        "<p>Ein Hip-Hop-Album mit viel Haltung und noch mehr Ironie.</p>"
        "<!-- HTML_TAG_END -->"
    )
    assert "Hip-Hop-Album" in ae._marker_description(page)


def test_text_parser_ignores_script_content():
    parser = ae._TextParser()
    parser.feed('<div>Echt<script>var x={"a":1};</script> Text</div>')
    text = " ".join(parser.parts)
    assert "var x" not in text
    assert "Echt" in text and "Text" in text


def test_looks_like_json():
    assert ae._looks_like_json('{"@context":"x"}') is True
    assert ae._looks_like_json("  [1,2,3]") is True
    assert ae._looks_like_json("Ganz normale Beschreibung.") is False


def test_description_prefers_prose_over_json(monkeypatch):
    # Enthält die Seite Marker-JSON und ein sauberes JSON-LD, gewinnt der
    # saubere Beschreibungstext, nicht der rohe JSON-Block.
    page = (
        "<!-- HTML_TAG_START -->"
        f'<script type="application/ld+json">{_LD_JSON}</script>'
        "<!-- HTML_TAG_END -->"
        f'<script type="application/ld+json">{_LD_JSON}</script>'
    )
    chosen = (
        ae._html_description(page)
        or ae._marker_description(page)
        or ae._json_ld_description(page)
    )
    assert chosen == "Saubere Beschreibung."
