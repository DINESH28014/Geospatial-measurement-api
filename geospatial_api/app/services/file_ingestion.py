import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Tuple, List, Optional
import fiona
import geopandas as gpd

from app.core.exceptions import (
    InvalidFileFormatException,
    SecurityValidationException,
    CorruptedFileException,
)
from app.core.logging import logger

# Enable KML / LIBKML support in Fiona
try:
    if "KML" not in fiona.drvsupport.supported_drivers:
        fiona.drvsupport.supported_drivers["KML"] = "rw"
    if "LIBKML" not in fiona.drvsupport.supported_drivers:
        fiona.drvsupport.supported_drivers["LIBKML"] = "rw"
except Exception as e:
    logger.warning(f"Could not configure Fiona KML driver support: {e}")


class FileIngestionService:
    """Service to handle file upload validation, zip inspection, archive extraction, and geospatial data parsing."""

    ALLOWED_EXTENSIONS = {".kml", ".zip"}

    @classmethod
    def validate_file_extension(cls, filename: str) -> str:
        """Validate filename extension."""
        if not filename:
            raise InvalidFileFormatException("Filename cannot be empty.")

        ext = Path(filename).suffix.lower()
        if ext not in cls.ALLOWED_EXTENSIONS:
            raise InvalidFileFormatException(
                f"Unsupported file extension '{ext}'. Only .kml and .zip Shapefile archives are supported."
            )
        return ext

    @classmethod
    def inspect_and_extract_zip(cls, zip_bytes: bytes, target_dir: str) -> List[str]:
        """
        Safely extract zip archive preventing Zip Slip / path traversal attacks.
        Returns list of extracted file paths.
        """
        extracted_paths = []
        try:
            zip_path = os.path.join(target_dir, "upload.zip")
            with open(zip_path, "wb") as f:
                f.write(zip_bytes)

            with zipfile.ZipFile(zip_path, "r") as zf:
                target_dir_abs = os.path.abspath(target_dir)

                for member in zf.infolist():
                    extracted_path = os.path.abspath(os.path.join(target_dir, member.filename))

                    # Zip Slip Security check: ensure target path is within target_dir
                    if not extracted_path.startswith(target_dir_abs):
                        logger.error(f"Security Alert: Zip Slip detected with entry '{member.filename}'")
                        raise SecurityValidationException(
                            f"Path traversal detected in zip entry '{member.filename}'."
                        )

                    zf.extract(member, target_dir)
                    extracted_paths.append(extracted_path)

        except zipfile.BadZipFile:
            raise CorruptedFileException("The uploaded file is not a valid zip archive or is corrupted.")
        except SecurityValidationException:
            raise
        except Exception as e:
            logger.error(f"Error extracting zip archive: {e}")
            raise CorruptedFileException(f"Failed to extract zip archive: {str(e)}")

        return extracted_paths

    @classmethod
    def parse_kml_file(cls, file_path: str) -> gpd.GeoDataFrame:
        """Parse KML file, including multi-layer files, into a single GeoDataFrame."""
        try:
            try:
                layers = fiona.listlayers(file_path)
            except Exception:
                layers = []

            gdfs = []
            if layers:
                for layer in layers:
                    try:
                        gdf_layer = gpd.read_file(file_path, driver="KML", layer=layer)
                        if not gdf_layer.empty:
                            gdfs.append(gdf_layer)
                    except Exception as layer_err:
                        logger.warning(f"Error reading KML layer '{layer}': {layer_err}")

            if not gdfs:
                # Try fallback standard read
                gdf = gpd.read_file(file_path)
                if gdf.empty:
                    raise CorruptedFileException("KML file contains no layers or valid feature data.")
                return gdf

            # Concatenate all non-empty layer GeoDataFrames
            unified_gdf = gpd.GeoDataFrame(
                pd_concat_gdfs(gdfs),
                crs=gdfs[0].crs if gdfs[0].crs is not None else None,
            )
            return unified_gdf

        except CorruptedFileException:
            raise
        except Exception as e:
            logger.error(f"KML parsing error: {e}")
            raise CorruptedFileException(f"Failed to parse KML file: {str(e)}")

    @classmethod
    def parse_shapefile_zip(cls, extracted_dir: str) -> gpd.GeoDataFrame:
        """Locate shapefile (.shp) and companion files inside extracted dir and read into GeoDataFrame."""
        shp_files = []
        for root, _, files in os.walk(extracted_dir):
            for file in files:
                if file.lower().endswith(".shp"):
                    shp_files.append(os.path.join(root, file))

        if not shp_files:
            raise CorruptedFileException("Zip archive does not contain any .shp Shapefile.")

        # Pick the primary shapefile
        shp_path = shp_files[0]
        base_path = os.path.splitext(shp_path)[0]

        # Verify essential companion files: .shx and .dbf
        missing_companions = []
        if not os.path.exists(base_path + ".shx") and not os.path.exists(base_path + ".SHX"):
            missing_companions.append(".shx")
        if not os.path.exists(base_path + ".dbf") and not os.path.exists(base_path + ".DBF"):
            missing_companions.append(".dbf")

        if missing_companions:
            raise CorruptedFileException(
                f"Missing required Shapefile companion files: {', '.join(missing_companions)}"
            )

        if not os.path.exists(base_path + ".prj") and not os.path.exists(base_path + ".PRJ"):
            logger.warning(f"Shapefile '{shp_path}' is missing a .prj projection file. CRS will default to EPSG:4326.")

        try:
            gdf = gpd.read_file(shp_path)
            if gdf.empty:
                raise CorruptedFileException("Shapefile contains no features or geometries.")
            return gdf
        except Exception as e:
            logger.error(f"Shapefile read error: {e}")
            raise CorruptedFileException(f"Failed to parse Shapefile: {str(e)}")

    @classmethod
    def process_upload(cls, filename: str, content: bytes) -> Tuple[gpd.GeoDataFrame, str]:
        """
        Main entry point for processing uploaded file bytes.
        Returns (GeoDataFrame, detected_crs_str).
        """
        ext = cls.validate_file_extension(filename)

        with tempfile.TemporaryDirectory() as temp_dir:
            if ext == ".kml":
                kml_path = os.path.join(temp_dir, "uploaded.kml")
                with open(kml_path, "wb") as f:
                    f.write(content)
                gdf = cls.parse_kml_file(kml_path)
            elif ext == ".zip":
                cls.inspect_and_extract_zip(content, temp_dir)
                gdf = cls.parse_shapefile_zip(temp_dir)
            else:
                raise InvalidFileFormatException(f"Unsupported extension: {ext}")

            raw_crs = gdf.crs
            crs_str = raw_crs.to_string() if raw_crs is not None else None
            return gdf, crs_str


def pd_concat_gdfs(gdfs: List[gpd.GeoDataFrame]) -> gpd.GeoDataFrame:
    """Helper to concatenate list of GeoDataFrames safely."""
    import pandas as pd
    combined_df = pd.concat(gdfs, ignore_index=True)
    return combined_df
