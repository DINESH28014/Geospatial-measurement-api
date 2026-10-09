import json
from typing import Dict, Any, Optional, Tuple
from shapely.geometry import base
import pandas as pd
import numpy as np

from app.core.logging import logger
from app.core.config import settings
from app.models.file_record import MeasurementStatus
from app.services.crs_projector import CRSProjectorService


class MeasurementEngineService:
    """Service to measure geometries (Area in m²/ha, Length in m/km) in projected CRS."""

    @classmethod
    def measure_geometry(
        cls, geometry: base.BaseGeometry
    ) -> Tuple[MeasurementStatus, Optional[float], Optional[float], Optional[float], Optional[float], Optional[str]]:
        """
        Calculates area and length measurements for a given Shapely geometry.
        Returns:
            (status, area_sq_meters, area_hectares, length_meters, length_km, error_message)
        """
        if geometry is None or geometry.is_empty:
            return (
                MeasurementStatus.UNSUPPORTED_GEOMETRY,
                None,
                None,
                None,
                None,
                "Empty or missing geometry",
            )

        geom_type = geometry.geom_type.upper()

        try:
            if "POLYGON" in geom_type:
                area_sq_m = float(geometry.area)
                area_ha = area_sq_m / 10000.0
                # Boundary length / perimeter
                perimeter_m = float(geometry.length)
                perimeter_km = perimeter_m / 1000.0
                return (
                    MeasurementStatus.COMPLETED,
                    round(area_sq_m, 4),
                    round(area_ha, 6),
                    round(perimeter_m, 4),
                    round(perimeter_km, 6),
                    None,
                )

            elif "LINESTRING" in geom_type:
                length_m = float(geometry.length)
                length_km = length_m / 1000.0
                return (
                    MeasurementStatus.COMPLETED,
                    None,
                    None,
                    round(length_m, 4),
                    round(length_km, 6),
                    None,
                )

            elif "POINT" in geom_type:
                return (
                    MeasurementStatus.MEASUREMENT_NOT_APPLICABLE,
                    None,
                    None,
                    None,
                    None,
                    "Points do not possess area or length properties.",
                )

            else:
                # GeometryCollection or other unsupported types
                return (
                    MeasurementStatus.UNSUPPORTED_GEOMETRY,
                    None,
                    None,
                    None,
                    None,
                    f"Unsupported geometry type '{geometry.geom_type}'",
                )

        except Exception as err:
            logger.error(f"Error measuring geometry type '{geometry.geom_type}': {err}")
            return (
                MeasurementStatus.FAILED,
                None,
                None,
                None,
                None,
                f"Measurement calculation failed: {str(err)}",
            )

    @classmethod
    def sanitize_properties(cls, row_series: pd.Series) -> Dict[str, Any]:
        """Convert row properties to JSON-serializable dictionary."""
        props = {}
        for col, val in row_series.items():
            if col.lower() in ("geometry", "geom"):
                continue

            # Convert numpy/pandas types
            if pd.isna(val):
                props[col] = None
            elif isinstance(val, (np.integer, np.int64, np.int32)):
                props[col] = int(val)
            elif isinstance(val, (np.floating, np.float64, np.float32)):
                props[col] = float(val)
            elif isinstance(val, (pd.Timestamp, np.datetime64)):
                props[col] = str(val)
            elif isinstance(val, bytes):
                props[col] = val.decode("utf-8", errors="ignore")
            else:
                try:
                    json.dumps(val)
                    props[col] = val
                except (TypeError, OverflowError):
                    props[col] = str(val)
        return props
