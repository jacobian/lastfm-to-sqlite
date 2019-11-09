from xml.dom import minidom
import pytest
from lastfm_to_sqlite import lastfm
import datetime as dt


@pytest.fixture
def track_node():
    doc = minidom.parseString(
        """
        <track>
            <artist mbid="artist-123">Aretha Franklin</artist>
            <name>Sisters Are Doing It For Themselves</name>
            <mbid>track-123</mbid>
            <album mbid="album-123"/>
            <url>www.last.fm/music/Aretha+Franklin/_/Sisters+Are+Doing+It+For+Themselves</url>
            <date uts="1213031819">9 Jun 2008, 17:16</date>
            <streamable>1</streamable>
        </track>
        """
    )
    return doc.documentElement


def test_extract_track_data(track_node: minidom.Node):
    data = lastfm._extract_track_data(track_node)
    assert data["artist"] == {"id": "artist-123", "name": "Aretha Franklin"}
    assert data["album"] == {
        "artist_id": "artist-123",
        "id": "album-123",
        "title": "(unknown album)",
    }
    assert data["track"] == {
        "album_id": "album-123",
        "id": "track-123",
        "title": "Sisters Are Doing It For Themselves",
    }
    assert data["play"] == {
        "track_id": "track-123",
        "timestamp": dt.datetime(2008, 6, 9, 13, 16, 59),
    }

