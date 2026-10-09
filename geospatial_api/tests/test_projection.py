import pytest
from pyproj import CRS
from shapely.geometry import Polygon, LineString

from app.services.crs_projector import CRSProjectorService


def test_normalize_source_crs():
    # Test None / missing CRS defaults to EPSG:4326
    default_crs = CRSProjectorService.normalize_source_crs(None)
    assert default_crs == CRS.from_epsg(4326)

    # Test valid EPSG string
    crs = CRSProjectorService.normalize_source_crs("EPSG:4326")
    assert crs == CRS.from_epsg(4326)

    # Test invalid string falls back to EPSG:4326
    fallback_crs = CRSProjectorService.normalize_source_crs("INVALID_CRS_CODE_99999")
    assert fallback_crs == CRS.from_epsg(4326)


def test_utm_zone_calculation():
    # New York City (Lat 40.76, Lon -73.98) -> Zone 18N (EPSG:32618)
    assert CRSProjectorService.get_utm_epsg_for_latlon(40.76, -73.98) == 32618

    # London (Lat 51.50, Lon -0.12) -> Zone 30N (EPSG:32630)
    assert CRSProjectorService.get_utm_epsg_for_latlon(51.50, -0.12) == 32630

    # Sydney (Lat -33.86, Lon 151.20) -> Zone 56S (EPSG:32756)
    assert CRSProjectorService.get_utm_epsg_for_latlon(-33.86, 151.20) == 32756


def test_reproject_to_projected_crs():
    # Create a polygon in WGS84 coordinates in NYC
    poly_wgs84 = Polygon([
        (-73.981886, 40.768094),
        (-73.958197, 40.800623),
        (-73.949614, 40.796853),
        (-73.973303, 40.764324),
        (-73.981886, 40.768094)
    ])

    source_crs = CRS.from_epsg(4326)
    proj_geom, proj_crs = CRSProjectorService.reproject_to_projected_crs(poly_wgs84, source_crs)

    assert proj_crs == "EPSG:32618"
    assert proj_geom.area > 100000  # Metric area in m² should be non-zero and substantial
    assert proj_geom.geom_type == "Polygon"
