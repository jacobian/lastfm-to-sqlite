import pylast
from xml.dom import Node
import datetime as dt
import hashlib


def recent_tracks(user: pylast.User):
    """
    This is similar to pylast.User.get_recent_tracks
    (https://github.com/pylast/pylast/blob/master/src/pylast/__init__.py#L2362),
    with a few specific additions to make the -to-sqlite part of this work
    better:

        1. Pulls the mbids from the recent tracks response, to get primary
           keys for artist/albums/tracks without having to make subsequent
           calls to the info API (which just slows things down)

        2. Returns dicts instead of pylast objects to make it easier
           to insert with sqlite-utils.

        3. Converts the timestamp to a datetime.

        4. It's a generator, because why not?
    """

    page = 1
    params = user._get_params()

    while True:
        params["page"] = page
        doc = user._request("user.getRecentTracks", cacheable=True, params=params)
        main = pylast.cleanup_nodes(doc).documentElement.childNodes[0]

        tracks = [e for e in main.childNodes if e.nodeType != Node.TEXT_NODE]
        for track in tracks:
            track_mbid = pylast._extract(track, "mbid")
            track_title = pylast._extract(track, "name")
            timestamp = dt.datetime.fromtimestamp(
                int(track.getElementsByTagName("date")[0].getAttribute("uts"))
            )
            artist_name = pylast._extract(track, "artist")
            artist_mbid = track.getElementsByTagName("artist")[0].getAttribute("mbid")
            album_title = pylast._extract(track, "album")
            album_mbid = track.getElementsByTagName("album")[0].getAttribute("mbid")

            # Handle missing titles
            if album_title is None:
                album_title = "(unknown album)"

            # If we don't have mbids, synthesize them
            if not artist_mbid:
                artist_mbid = (
                    "md5:" + hashlib.md5(artist_name.encode("utf8")).hexdigest()
                )
            if not album_mbid:
                h = hashlib.md5()
                h.update(artist_mbid.encode("utf8"))
                h.update(album_title.encode("utf8"))
                album_mbid = "md5:" + h.hexdigest()
            if not track_mbid:
                h = hashlib.md5()
                h.update(album_mbid.encode("utf8"))
                h.update(track_title.encode("utf8"))
                track_mbid = "md5:" + h.hexdigest()

            # TODO: we could fetch a _bunch_ of additional information here
            # by hitting artist.getInfo / album.getInfo / track.getInfo.
            # That would slow things down but could be danged cool.

            yield {
                "artist": {"id": artist_mbid, "name": artist_name},
                "album": {
                    "id": album_mbid,
                    "title": album_title,
                    "artist_id": artist_mbid,
                },
                "track": {
                    "id": track_mbid,
                    "album_id": album_mbid,
                    "title": track_title,
                },
                "play": {"track_id": track_mbid, "timestamp": timestamp},
            }

        page += 1
        total_pages = int(main.getAttribute("totalPages"))
        if page > total_pages:
            break

