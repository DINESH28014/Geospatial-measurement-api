import math
from typing import Tuple, Optional
import pyproj
from pyproj import CRS, Transformer
from shapely.geometry import base
from shapely import transform
from app.core.logging import logger
from app.core.config import settings


class CRSProjectorService:
    """Service to handle Coordinate Reference System extraction, validation, and dynamic reprojection."""

    @staticmethod
    def normalize_source_crs(raw_crs: Optional[object]) -> CRS:
        """Extract and normalize source CRS. If missing/invalid, default safely to EPSG:4326 with warning."""
        if raw_crs is None:
            logger.warning("Source CRS is missing/undefined. Defaulting to EPSG:4326.")
            return CRS.from_epsg(4326)

        try:
            if isinstance(raw_crs, CRS):
                return raw_crs
            return CRS.from_user_input(raw_crs)
        except Exception as err:
            logger.warning(
                f"Could not parse source CRS '{raw_crs}': {err}. Defaulting to EPSG:4326."
            )
            return CRS.from_epsg(4326)

    @staticmethod
    def get_utm_epsg_for_latlon(lat: float, lon: float) -> int:
        """Determine appropriate WGS 84 UTM EPSG code given latitude and longitude."""
        # Normalize longitude between -180 and 180
        lon = (lon + 180) % 360 - 180
        utm_zone = int(math.floor((lon + 180) / 6)) + 1
        utm_zone = max(1, min(60, utm_zone))

        if lat >= 0:
            epsg_code = 32600 + utm_zone
        else:
            epsg_code = 32700 + utm_zone

        return epsg_code

    @classmethod
    def reproject_to_projected_crs(
        cls,
        geometry: base.BaseGeometry,
        source_crs: CRS,
    ) -> Tuple[base.BaseGeometry, str]:
        """
        Dynamically reproject a geometry from source CRS to an appropriate metric projected CRS.
        
        Steps:
        1. If source CRS is not EPSG:4326, transform geometry to EPSG:4326 to derive lat/lon centroid.
        2. Calculate centroid in lat/lon.
        3. Determine local UTM zone EPSG code.
        4. Transform geometry from source CRS to the target local UTM projected CRS.
        """
        wgs84 = CRS.from_epsg(4326)

        # First, get geometry in WGS84 for centroid estimation
        if source_crs != wgs84:
            try:
                to_wgs84 = Transformer.from_crs(source_crs, wgs84, always_xy=True).transform
                wgs84_geom = transform(geometry, to_wgs84, interleaved=False)
            except Exception as e:
                logger.warning(f"Failed to transform geometry to WGS84 for centroid calculation: {e}")
                wgs84_geom = geometry
        else:
            wgs84_geom = geometry

        # Calculate centroid in WGS84
        if wgs84_geom.is_empty:
            return geometry, source_crs.to_string()

        centroid = wgs84_geom.centroid
        lon, lat = centroid.x, centroid.y

        # Determine target projected CRS (UTM)
        try:
            target_epsg = cls.get_utm_epsg_for_latlon(lat=lat, lon=lon)
            target_crs = CRS.from_epsg(target_epsg)
            target_crs_str = f"EPSG:{target_epsg}"
        except Exception as e:
            logger.warning(f"Failed to determine UTM zone ({e}). Falling back to ESRI:54009 (World Equal Area).")
            target_crs = CRS.from_user_input("ESRI:54009")
            target_crs_str = "ESRI:54009"

        # Transform from source_crs to target_crs
        if source_crs == target_crs:
            return geometry, target_crs_str

        transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
        projected_geom = transform(geometry, transformer.transform, interleaved=False)

        return projected_geom, target_crs_str
