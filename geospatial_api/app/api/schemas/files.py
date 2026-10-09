from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class MeasurementDetail(BaseModel):
    area_sq_meters: Optional[float] = Field(None, description="Area in square meters (Polygon/MultiPolygon)")
    area_hectares: Optional[float] = Field(None, description="Area in hectares (Polygon/MultiPolygon)")
    length_meters: Optional[float] = Field(None, description="Length/Perimeter in meters")
    length_km: Optional[float] = Field(None, description="Length/Perimeter in kilometers")

    model_config = ConfigDict(from_attributes=True)


class FileUploadResponse(BaseModel):
    id: str = Field(..., description="Unique file record UUID")
    filename: str = Field(..., description="Original file name")
    status: str = Field(..., description="Processing status (PENDING, PROCESSING, COMPLETED, FAILED)")
    feature_count: int = Field(..., description="Number of extracted geospatial features")
    crs: Optional[str] = Field(None, description="Detected source CRS")

    model_config = ConfigDict(from_attributes=True)


class FileDetailResponse(BaseModel):
    id: str
    filename: str
    file_size: int
    file_type: str
    status: str
    error_message: Optional[str] = None
    feature_count: int
    detected_crs: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FeatureMeasurementResponse(BaseModel):
    feature_id: str = Field(..., description="Index or source feature ID")
    geometry_type: str = Field(..., description="Geometry type (Polygon, LineString, Point, etc.)")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Feature attributes dictionary")
    source_crs: Optional[str] = Field(None, description="Source Coordinate Reference System")
    projected_crs_used: Optional[str] = Field(None, description="Projected CRS used for measurement")
    measurement_status: str = Field(..., description="COMPLETED, MEASUREMENT_NOT_APPLICABLE, UNSUPPORTED_GEOMETRY, FAILED")
    measurements: MeasurementDetail = Field(..., description="Calculated area and length metric values")
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedFeatureMeasurementsResponse(BaseModel):
    file_id: str = Field(..., description="UUID of the parent file record")
    total: int = Field(..., description="Total feature measurement count")
    page: int = Field(..., description="Current page number (1-based)")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total available pages")
    items: List[FeatureMeasurementResponse] = Field(..., description="List of feature measurement records")

    model_config = ConfigDict(from_attributes=True)
