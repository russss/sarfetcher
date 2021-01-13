# SARFetcher

Fetches Sentinel-1 synthetic aperture radar imagery for a particular area, and apply some processing to combine bands into an RGB image.

## Requirements

* Python 3
* GDAL libraries and python bindings installed locally (you generally want to install these bindings using the OS package manager, not pip)
* A local postgres database with PostGIS installed.
* A user account on the [Copernicus Open Access Hub](https://scihub.copernicus.eu/) (scihub).

## Installation

Git clone this repo and run `pip3 install .`. It's best to install this using the system python rather than a virtualenv so that the system GDAL library is used.

## Configuration

Create `sarfetcher.cfg` either in the local directory or in `/etc`:
```
[db]
url = postgresql://user@host/sentinel1

[sentinel]
username = scihub_username
password = scihub_password
```

## How to use

Run `sarfetcher import -d 30`. This will initialise the database and import the last 30 days of image metadata from the Sentinel hub into the PostGIS database.

Now you need to insert one row into the `search_area` table, containing a multipolygon representing the area you want to download. An example for the North Sea/English Channel is below, but if you need to specify a custom area, it's probably easiest to add the `search_area` table to QGIS and create the polygon.

Once this is complete, you can fetch the images which cover your search area:

`sarfetcher fetch ./output_directory`

This will download and process a set of images, putting the finished .tif files in `output_directory`. It will delete any images from that directory which are no longer current. For the North Sea/English Channel area this dataset is approximately 55GB in size.

The `import` and `fetch` steps can be run periodically to update the data.

### North Sea and English Channel polygon
```
INSERT INTO search_area(geom) VALUES (ST_GeomFromEWKT('SRID=4326;POLYGON((5.23696369636964 61.9808580858086,-3.84554455445545 58.5379537953796,-2.42508250825082 57.2178217821782,-2.5993399339934 56.1881188118812,-1.63300330033003 55.5491749174918,-1.22112211221122 54.6884488448845,-0.122772277227722 54.1181518151815,1.70957095709571 50.9551155115512,-4.14125412541254 50.4693069306931,-2.43036303630363 48.3993399339934,1.98415841584158 50.2580858085809,5.74389438943894 53.2574257425743,8.9755775577557853.6798679867987,8.48976897689769 56.8481848184819,11.8481848184818 57.819801980198,11.0244224422442 59.6363036303631,7.75049504950495 57.9887788778878,5.63828382838284 58.4957095709571,4.8990099009901 60.7135313531353,5.23696369636964 61.9808580858086))'));
```
## Generating tiled map

Once you have the .tif files downloaded, you can use GDAL to generate tiles for a web map. First, generate a `.vrt` file,
which acts as an index of all the image files (this is close to instant):

	gdalbuildvrt -srcnodata "0 0 0" -hidenodata ./sar.vrt ./output_directory/*.tif

Now, use `gdal2tiles.py` to generate the tiles:

	gdal2tiles.py ./sar.vrt /path/to/output
