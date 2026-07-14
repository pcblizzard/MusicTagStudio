from mutagen.flac import FLAC


def read_metadata(filepath):
    try:
        audio = FLAC(filepath)

        return {
            "artist": get_tag(audio, "artist"),
            "album": get_tag(audio, "album"),
            "title": get_tag(audio, "title"),
            "year": get_tag(audio, "date"),
            "path": filepath
        }

    except Exception:
        return {
            "artist": "",
            "album": "",
            "title": "",
            "year": "",
            "path": filepath
        }


def get_tag(audio, tag):
    value = audio.get(tag)

    if value:
        return value[0]

    return ""