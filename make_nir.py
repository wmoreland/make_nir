import os
import sys
import argparse
import subprocess
from osgeo import gdal


def combine_bands(workspace, tiff=False, overwrite=True):

    # Get list of Sentinel 2 image sets in given directory
    raster_list = [
        os.path.join(dir_path, filename)
        for dir_path, _, files in os.walk(workspace)
        for filename in files
        if filename.endswith("B08.jp2") and "IMG_DATA" in dir_path
    ]
    print(f"Images found: {len(raster_list)}")

    # This line suppresses FutureWarning from gdal
    gdal.UseExceptions()

    # Loop over every image set
    for raster in raster_list:
        print(f"\nStarted on {os.path.basename(raster)}")

        # Set up names for output files
        vrt_name = raster.replace("B08.jp2", "NIR_B843.vrt")
        reprojected_vrt_name = raster.replace("B08.jp2", "NIR_B843_ISN93.vrt")
        geotiff_name = raster.replace("B08.jp2", "NIR_B843_ISN93.tif")

        if tiff:
            if os.path.exists(geotiff_name):
                if overwrite:
                    print(
                        f"\n{os.path.basename(geotiff_name)} already exists - deleting it"
                    )
                    os.remove(geotiff_name)
                else:
                    print(
                        f"\n{os.path.basename(geotiff_name)} already exists - stopping\n"
                    )
                    continue
        else:
            if os.path.exists(reprojected_vrt_name):
                if overwrite:
                    print(
                        f"\n{os.path.basename(reprojected_vrt_name)} already exists - deleting it"
                    )
                    os.remove(reprojected_vrt_name)
                else:
                    print(
                        f"\n{os.path.basename(reprojected_vrt_name)} already exists - stopping\n"
                    )
                    continue

        bands = [
            raster,
            raster.replace("B08.jp2", "B04.jp2"),
            raster.replace("B08.jp2", "B03.jp2"),
        ]

        # Build VRT with separate bands
        print(f"\nBuilding {'intermediate ' if tiff else ''}virtual raster")
        subprocess.run(
            [
                "gdalbuildvrt",
                "-separate",
                vrt_name,
                *bands,
            ],
            check=True,
        )

        if not tiff:
            print("\nReprojecting virtual raster")

            # Using Popen to allow control of stdout
            process = subprocess.Popen(
                [
                    "gdalwarp",
                    "-of",
                    "VRT",
                    "-s_srs",
                    "EPSG:32627",
                    "-t_srs",
                    "EPSG:3057",
                    "-wo",
                    "NUM_THREADS=ALL_CPUS",
                    "-multi",
                    vrt_name,
                    reprojected_vrt_name,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            # Tidying up stdout
            for line in process.stdout:
                if "[1/1]" in line:
                    # This handles the progress updates
                    line = line.replace("[1/1]", "\n[1/1]")
                print(line, end="")

            process.stdout.close()
            process.wait()

        else:
            print("\nReprojecting and saving geotiff")
            process = subprocess.Popen(
                [
                    "gdalwarp",
                    "-of",
                    "GTiff",
                    "-co",
                    "COMPRESS=LZW",
                    "-s_srs",
                    "EPSG:32627",
                    "-t_srs",
                    "EPSG:3057",
                    "-wo",
                    "NUM_THREADS=ALL_CPUS",
                    "-multi",
                    vrt_name,
                    geotiff_name,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            # Tidying up stdout
            for line in process.stdout:
                if "[1/1]" in line:
                    # This handles the progress updates
                    line = line.replace("[1/1]", "\n[1/1]")
                print(line, end="")

            process.stdout.close()
            process.wait()

            # Open the output TIFF and build pyramids
            dataset = gdal.Open(geotiff_name, gdal.GA_Update)
            if dataset is not None:
                print("\nBuilding pyramids for geotiff")
                subprocess.run(
                    [
                        "gdaladdo",
                        "-ro",
                        "--config",
                        "COMPRESS_OVERVIEW",
                        "LZW",
                        geotiff_name,
                        "2",
                        "4",
                        "8",
                        "16",
                        "32",
                        "64",
                        "128",
                        "256",
                    ],
                    check=True,
                )
                print(f"Pyramids built for {geotiff_name}")
            else:
                print(f"Failed to open {geotiff_name} for pyramid building.")

        print(
            f"\nCompleted processing of {os.path.basename(geotiff_name) if tiff else os.path.basename(reprojected_vrt_name)}\n"
        )


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Combine bands 8, 4, and 3 from Sentinel 2 images to make a false-colour near-infrared image"
    )

    parser.add_argument(
        "workspace",
        type=str,
        help="Path to a directory containing one or more Sentinel 2 image sets",
    )
    parser.add_argument(
        "-t",
        "--tiff",
        action="store_true",
        dest="tiff",
        help="Set this flag to output in GeoTiff format (default is VRT)",
    )
    parser.add_argument(
        "-n",
        "--no-overwrite",
        action="store_false",
        dest="overwrite",
        help="Set this flag to prevent overwriting existing files (default is to overwrite)",
    )

    # Parse arguments from the command line
    args = parser.parse_args()

    # Use the parsed arguments
    combine_bands(args.workspace, args.tiff, args.overwrite)

else:
    # This block will run only if the script is imported
    print("Script is imported as a module")
