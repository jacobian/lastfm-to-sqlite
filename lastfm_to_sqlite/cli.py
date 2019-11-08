import click
import os
import json
import sqlite_utils
from . import lastfm
import dateutil.parser


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

    db = sqlite_utils.Database(database)

    if since and db["plays"].exists:
        since_date = db.conn.execute("select max(timestamp) from plays").fetchone()[0]
    if since_date:
        since_date = dateutil.parser.parse(since_date)

    auth = json.load(open(auth))
    network = lastfm.get_network(
        auth["lastfm_network"],
        key=auth["lastfm_api_key"],
        secret=auth["lastfm_shared_secret"],
    )

    user = network.get_user(auth["lastfm_username"])
    playcount = user.get_playcount()
    history = lastfm.recent_tracks(user, since_date)

    # FIXME: the progress bar is wrong if there's a since_date
    with click.progressbar(
        history, length=playcount, label="Importing plays", show_pos=True
    ) as progress:
        for track in progress:
            lastfm.save_artist(db, track["artist"])
            lastfm.save_album(db, track["album"])
            lastfm.save_track(db, track["track"])
            lastfm.save_play(db, track["play"])
