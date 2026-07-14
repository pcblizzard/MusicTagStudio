from mutagen.flac import FLAC


def load_metadata(filepath):
    audio = FLAC(filepath)

    return {
        "title": audio.get("title", [""])[0],
        "artist": audio.get("artist", [""])[0],
        "album": audio.get("album", [""])[0],
        "year": audio.get("date", [""])[0],
    }


def save_metadata(filepath, title, artist, album, year):

    audio = FLAC(filepath)

    audio["title"] = title
    audio["artist"] = artist
    audio["album"] = album
    audio["date"] = year

    audio.save()