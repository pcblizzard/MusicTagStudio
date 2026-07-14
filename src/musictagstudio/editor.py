from mutagen.flac import FLAC


def save_metadata(filepath, title, artist, album, year):

    audio = FLAC(filepath)

    audio["title"] = title
    audio["artist"] = artist
    audio["album"] = album
    audio["date"] = year

    audio.save()