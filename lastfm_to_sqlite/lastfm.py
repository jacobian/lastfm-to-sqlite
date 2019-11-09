import datetime as dt
import hashlib
from typing import Dict
from xml.dom.minidom import Node

import pylast
from sqlite_utils import Database


def recent_tracks(user: pylast.User, since: dt.datetime):
    """
    This is similar to pylast.User.get_recent_tracks
    (https://github.com/pylast/pylast/blob/master/src/pylast/__init__.py#L2362),
    with a few specific additions to make the -to-sqlite part of this work
    better:

        1. Pulls the mbids from the recent tracks response, to get primary
           keys for artist/albums/tracks without having to make subsequent
           calls to the info API (which just slows things down)

        2. Returns dicts ready for upsert'ing with sqlite-utils.

        3. Converts the timestamp to a datetime.

        4. It's a generator so that the caller can display a progress bar.
    """

    page = 1
    params = dict(user._get_params(), limit=200)
    if since:
        params["from"] = int(since.timestamp())

    while True:
        params["page"] = page
        doc = user._request("user.getRecentTracks", cacheable=True, params=params)
        main = pylast.cleanup_nodes(doc).documentElement.childNodes[0]
        for node in main.childNodes:
            if node.nodeType != Node.TEXT_NODE:
                yield _extract_track_data(node)

        page += 1
        total_pages = int(main.getAttribute("totalPages"))
        if page > total_pages:
            break


def _extract_track_data(track: Node):
    track_mbid = pylast._extract(track, "mbid")
    track_title = pylast._extract(track, "name")
    timestamp = dt.datetime.fromtimestamp(
        int(track.getElementsByTagName("date")[0].getAttribute("uts"))
    )
    artist_name = pylast._extract(track, "artist")
    artist_mbid = track.getElementsByTagName("artist")[0].getAttribute("mbid")
    album_title = pylast._extract(track, "album")
    album_mbid = track.getElementsByTagName("album")[0].getAttribute("mbid")

    # TODO: could call track/album/artist.getInfo here, and get more info?

    # Handle missing titles
    if album_title is None:
        album_title = "(unknown album)"

    # If we don't have mbids, synthesize them
    if not artist_mbid:
        artist_mbid = "md5:" + hashlib.md5(artist_name.encode("utf8")).hexdigest()
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

    return {
        "artist": {"id": artist_mbid, "name": artist_name},
        "album": {"id": album_mbid, "title": album_title, "artist_id": artist_mbid},
        "track": {"id": track_mbid, "album_id": album_mbid, "title": track_title},
        "play": {"track_id": track_mbid, "timestamp": timestamp},
    }


def get_network(name: str, key: str, secret: str):
    cls = {"lastfm": pylast.LastFMNetwork, "librefm": pylast.LibreFMNetwork}[name]
    network = cls(api_key=key, api_secret=secret)
    network.enable_caching()
    network.enable_rate_limit()
    return network


def save_artist(db: Database, data: Dict):
    db["artists"].upsert(data, pk="id", column_order=["id", "name"], not_null=["name"])


def save_album(db: Database, data: Dict):
    db["albums"].upsert(
        data, pk="id", foreign_keys=["artist_id"], not_null=["id", "artist_id", "title"]
    )


def save_track(db: Database, data: Dict):
    db["tracks"].upsert(
        data, pk="id", foreign_keys=["album_id"], not_null=["id", "album_id", "title"]
    )


def save_play(db: Database, data: Dict):
    db["plays"].upsert(data, pk=["timestamp", "track_id"], foreign_keys=["track_id"])
