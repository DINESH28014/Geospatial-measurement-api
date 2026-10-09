import os
import io
import zipfile
import pytest
import geopandas as gpd

from app.core.exceptions import (
    InvalidFileFormatException,
    SecurityValidationException,
    CorruptedFileException,
)
from app.services.file_ingestion import FileIngestionService


def test_validate_file_extension():
    assert FileIngestionService.validate_file_extension("data.kml") == ".kml"
    assert FileIngestionService.validate_file_extension("archive.ZIP") == ".zip"

    with pytest.raises(InvalidFileFormatException):
        FileIngestionService.validate_file_extension("image.png")

    with pytest.raises(InvalidFileFormatException):
        FileIngestionService.validate_file_extension("")


def test_zip_slip_security_prevention(tmp_path):
    """Verify that Zip Slip path traversal attempt raises SecurityValidationException."""
    zip_bytes = io.BytesIO()
    with zipfile.ZipFile(zip_bytes, "w") as zf:
        # Malicious filename attempting path traversal
        zf.writestr("../../../malicious.txt", "malicious payload")

    target_dir = str(tmp_path / "extract_test")
    os.makedirs(target_dir, exist_ok=True)

    with pytest.raises(SecurityValidationException):
        FileIngestionService.inspect_and_extract_zip(zip_bytes.getvalue(), target_dir)


def test_bad_zip_file_handling(tmp_path):
    """Verify corrupted zip content raises CorruptedFileException."""
    bad_bytes = b"Not a valid zip content"
    target_dir = str(tmp_path / "bad_zip_test")
    os.makedirs(target_dir, exist_ok=True)

    with pytest.raises(CorruptedFileException):
        FileIngestionService.inspect_and_extract_zip(bad_bytes, target_dir)


def test_missing_shapefile_companions(tmp_path):
    """Verify shapefile missing .shx / .dbf companion files raises CorruptedFileException."""
    extract_dir = str(tmp_path / "missing_companion")
    os.makedirs(extract_dir, exist_ok=True)

    # Create only a dummy .shp file without .shx/.dbf
    dummy_shp = os.path.join(extract_dir, "test.shp")
    with open(dummy_shp, "w") as f:
        f.write("dummy")

    with pytest.raises(CorruptedFileException):
        FileIngestionService.parse_shapefile_zip(extract_dir)


def test_parse_valid_kml(sample_data_dir):
    kml_path = os.path.join(sample_data_dir, "sample_polygon.kml")
    gdf = FileIngestionService.parse_kml_file(kml_path)

    assert isinstance(gdf, gpd.GeoDataFrame)
    assert not gdf.empty
    assert len(gdf) == 1
    assert gdf.iloc[0].geometry.geom_type == "Polygon"
