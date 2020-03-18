import gdal
import glob
from os import path
from osgeo.gdal_array import CopyDatasetInfo
import numpy as np


def open_glob(pathname):
    results = glob.glob(pathname)
    return gdal.Open(results[0])


def get_band(ds):
    return ds.GetRasterBand(1).ReadAsArray()


def process_band(band, gain, clip):
    return np.clip(band * gain, 0, clip) * (255 // clip)


def log_contrast(band, gain=1):
    band = gain * np.nan_to_num(np.log(1 + band))
    return band * (255 / np.amax(band))


def convert(src_path, out_path):
    vh_file = open_glob(path.join(src_path, "*.SAFE", "measurement", "s1?-iw-grd-vh-*.tiff"))
    vv_file = open_glob(path.join(src_path, "*.SAFE", "measurement", "s1?-iw-grd-vv-*.tiff"))

    vh = get_band(vh_file)
    vv = get_band(vv_file)

    r = process_band(vh, 1, 200)
    g = log_contrast(vv / vh, 0.8)
    b = process_band(vv, 1, 250)

    ds_intermediate = gdal.GetDriverByName("MEM").Create(
        out_path,
        vh.shape[1],
        vh.shape[0],
        3,
        gdal.GDT_Byte
    )
    CopyDatasetInfo(vh_file, ds_intermediate)
    ds_intermediate.GetRasterBand(1).WriteArray(r)
    ds_intermediate.GetRasterBand(2).WriteArray(g)
    ds_intermediate.GetRasterBand(3).WriteArray(b)

    # Warp to the output file. The Sentinel TIFF files are georeferenced with GCPs -
    # this uses the GCPs to generate a proper transform which the VRT tooling will accept,
    # and also does the conversion to web mercator.
    gdal.Warp(
        out_path,
        ds_intermediate,
        srcSRS="EPSG:4326",
        dstSRS="EPSG:3857",
        outputType=gdal.GDT_Byte,
        multithread=True,
        creationOptions=["COMPRESS=DEFLATE", "INTERLEAVE=BAND", "PHOTOMETRIC=RGB"],
    )
