import click
import os
import json
import sqlite_utils
import pylast
from . import lastfm


@click.group()
@click.version_option()
def cli():
    "Save data from last.fm/libre.fm to a SQLite database"


@cli.command()
@click.option(
    "-a",
    "--auth",
    type=click.Path(file_okay=True, dir_okay=False, allow_dash=False),
    default="auth.json",
    help="Path to save token to",
    show_default=True,
)
@click.option(
    "-n",
    "--network",
    type=click.Choice(["lastfm", "librefm"]),
    help="which scrobble network to use. this is saved to the auth file.",
    default="lastfm",
    show_default=True,
)
def auth(auth, network):
    "Save authentication credentials to a JSON file"

    if network == "lastfm":
        click.echo(
            f"Create an API account here: https://www.last.fm/api/account/create"
        )
    elif network == "librefm":
        click.echo(f"Create an API account here: xxxfixme")
    click.echo()
    username = click.prompt("Your username")
    api_key = click.prompt("API Key")
    shared_secret = click.prompt("Shared Secret")

    # TODO: we could test that this works by calling Network.get_user()

    auth_data = json.load(open(auth)) if os.path.exists(auth) else {}
    auth_data.update(
        {
            "lastfm_network": network,
            "lastfm_username": username,
            "lastfm_api_key": api_key,
            "lastfm_shared_secret": shared_secret,
        }
    )
    json.dump(auth_data, open(auth, "w"))


@cli.command()
@click.argument(
    "database",
    required=True,
    type=click.Path(file_okay=True, dir_okay=False, allow_dash=False),
)
@click.option(
    "-a",
    "--auth",
    type=click.Path(file_okay=True, dir_okay=False, allow_dash=False, exists=True),
    default="auth.json",
    help="Path to read auth token from",
    show_default=True,
)
@click.option(
    "--since",
    is_flag=True,
    default=False,
    help="Pull new posts since last saved post in DB",
)
@click.option("--since-date", metavar="DATE", help="Pull new posts since DATE")
def plays(database, auth, since, since_date):
    if since and since_date:
        raise click.UsageError("use either --since or --since-date, not both")

    auth = json.load(open(auth))
    if auth["lastfm_network"] == "lastfm":
        network = pylast.LastFMNetwork(
            api_key=auth["lastfm_api_key"],
            api_secret=auth["lastfm_shared_secret"],
            username=auth["lastfm_username"],
        )
    elif auth["lastfm_network"] == "librefm":
        network = pylast.LibreFMNetwork(
            api_key=auth["lastfm_api_key"],
            api_secret=auth["lastfm_shared_secret"],
            username=auth["lastfm_username"],
        )
    else:
        raise click.ClickException(
            f"invalid value for network: {auth['lastfm_network']}"
        )

    db = sqlite_utils.Database(database)
    artists = db.table(
        "artists", pk="id", column_order=["id", "name"], not_null=["name"]
    )
    albums = db.table(
        "albums",
        pk="id",
        column_order=["id", "artist_id", "title"],
        foreign_keys=["artist_id"],
        not_null=["id", "artist_id", "title"],
    )
    tracks = db.table(
        "tracks",
        pk="id",
        column_order=["id", "album_id", "title"],
        foreign_keys=["album_id"],
        not_null=["id", "album_id", "title"],
    )
    plays = db.table(
        "plays",
        pk=["timestamp", "track_id"],
        column_order=["timestamp", "track_id"],
        foreign_keys=["track_id"],
    )

    user = network.get_user(auth["lastfm_username"])
    playcount = user.get_playcount()
    history = lastfm.recent_tracks(user)
    with click.progressbar(
        history, length=playcount, label="Importing plays", show_pos=True
    ) as progress:
        for track in progress:
            artists.upsert(track["artist"])
            albums.upsert(track["album"])
            tracks.upsert(track["track"])
            plays.upsert(track["play"])
