import click
import requests
import shutil
import tempfile
import os
import configparser
from os import path
from datetime import datetime, timedelta
from sqlalchemy import select, desc
from dateutil.parser import parse as parse_date
from geoalchemy2.shape import to_shape, from_shape
from zipfile import ZipFile

from .db import images, get_db, search_area
from .convert import convert


def load_config():
    config = configparser.ConfigParser()
    config.read(["sarfetcher.cfg", "/etc/sarfetcher.cfg"])
    return config


@click.group()
def cli():
    """ Sentinel-1 SAR imagery fetcher """
    pass


def parse_entry(entry):
    data = {"title": entry["title"]}

    for val in entry["date"]:
        data[val["name"]] = parse_date(val["content"])

    for val in entry["str"]:
        data[val["name"]] = val["content"]

    for val in entry["int"]:
        data[val["name"]] = int(val["content"])

    return data


def search(query, username, password):
    offset = 0

    while True:
        res = requests.get(
            f"https://scihub.copernicus.eu/dhus/search?q={query}&rows=100&start={offset}"
            "&sortedby=beginposition&order=desc&format=json",
            auth=(username, password),
        )
        res.raise_for_status()
        if "entry" not in res.json()["feed"]:
            return

        yield from (parse_entry(entry) for entry in res.json()["feed"]["entry"])
        offset += 100


@cli.command("import")
@click.option("--days", "-d", default=1)
def import_(days):
    """ Import image metadata """
    config = load_config()
    conn = get_db(config["db"]["url"])
    start_date = datetime.now() - timedelta(days=days)
    click.echo(f"Importing images from {start_date}")

    inserted, existing = 0, 0
    for item in search(
        "platformname:Sentinel-1 AND producttype:GRD AND "
        f"beginPosition:[{start_date.isoformat()}Z TO NOW]",
        config["sentinel"]["username"],
        config["sentinel"]["password"],
    ):
        if conn.execute(
            select([images]).where(images.c.uuid == item["uuid"])
        ).fetchone():
            existing += 1
        else:
            inserted += 1
            conn.execute(
                images.insert().values(
                    uuid=item["uuid"],
                    title=item["title"],
                    start_date=item["beginposition"],
                    geom="SRID=4326;" + item["footprint"],
                )
            )
        if (inserted + existing) % 100 == 0:
            click.echo(f"Inserted {inserted}, existing {existing}")
    click.echo(
        f"Import complete. {inserted} new images, {existing} images already imported."
    )


def download_file(uuid, dest, username, password):
    url = f"https://scihub.copernicus.eu/dhus/odata/v1/Products('{uuid}')/$value"
    with requests.get(url, stream=True, auth=(username, password)) as res:
        res.raise_for_status()
        shutil.copyfileobj(res.raw, dest)


@cli.command()
@click.option(
    "--target",
    "-t",
    default=0.01,
    help="max area remaining when complete (square degrees)",
)
@click.argument("dest_path")
def fetch(target, dest_path):
    """ Fetch and convert image files to cover search area """
    config = load_config()
    conn = get_db(config["db"]["url"])
    seen = set()
    to_fetch = set()

    area_row = conn.execute(select([search_area])).fetchone()
    if area_row is None:
        click.echo("No search area in database!")
        return

    area = to_shape(area_row[1])

    dest_path = path.abspath(dest_path)
    if path.exists(dest_path) and not path.isdir(dest_path):
        click.echo(f"Path {dest_path} exists and is not a directory!")
        return

    if not path.exists(dest_path):
        os.makedirs(dest_path)

    click.echo("Calculating images to fetch...")
    while area.area > target:
        res = conn.execute(
            select(
                [images],
                images.c.geom.intersects(from_shape(area, srid=4326))
                & images.c.geom.ST_Intersects(from_shape(area, srid=4326))
                & ~images.c.uuid.in_(seen),
            ).order_by(desc(images.c.start_date))
        ).first()
        if res is None:
            break

        seen.add(res.uuid)
        new_area = area.difference(to_shape(res[images.c.geom]))
        if (area.area - new_area.area) < 0.01:
            continue

        to_fetch.add(res.uuid)
        area = new_area

    click.echo(
        f"Search complete - images to fetch {len(to_fetch)}, area remaining {area.area:.3f}, target {target}"
    )

    try:
        temp_dir = tempfile.mkdtemp(prefix="sentinel-sar")
        for uuid in to_fetch:
            dest_file = os.path.join(dest_path, uuid + ".tif")
            if os.path.exists(dest_file):
                click.echo(f"File {uuid}.tif already exists")
                continue

            click.echo(f"Fetching file {uuid}...")
            zip_file = os.path.join(temp_dir, uuid + ".zip")
            img_dir = os.path.join(temp_dir, uuid)

            with open(zip_file, "wb") as temp:
                download_file(
                    uuid,
                    temp,
                    config["sentinel"]["username"],
                    config["sentinel"]["password"],
                )

            with ZipFile(zip_file, "r") as zipfile:
                zipfile.extractall(img_dir)
            os.remove(zip_file)

            click.echo("Converting...")
            convert(img_dir, dest_file)
            shutil.rmtree(img_dir)
    finally:
        shutil.rmtree(temp_dir)

    existing = set(
        f.split(".")[0]
        for f in os.listdir(dest_path)
        if path.isfile(path.join(dest_path, f))
    )
    for filename in existing - to_fetch:
        os.remove(path.join(dest_path, filename))
