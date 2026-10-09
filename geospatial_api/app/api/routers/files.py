import json
from typing import Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import (
    GeospatialAPIException,
    InvalidFileFormatException,
    SecurityValidationException,
    CorruptedFileException,
)
from app.core.logging import logger
from app.models.file_record import FileRecord, FeatureMeasurement, FileStatus
from app.api.schemas.files import (
    FileUploadResponse,
    FileDetailResponse,
    FeatureMeasurementResponse,
    PaginatedFeatureMeasurementsResponse,
    MeasurementDetail,
)
from app.services.file_ingestion import FileIngestionService
from app.services.crs_projector import CRSProjectorService
from app.services.measurement_engine import MeasurementEngineService

router = APIRouter(prefix="/files", tags=["Geospatial Files"])


@router.post(
    "/",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and process geospatial file (.kml or .zip Shapefile)",
)
async def upload_and_process_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a KML file or Zipped Shapefile archive to parse and calculate metrics.
    - Validates file extensions and prevents Zip Slip path traversal.
    - Reprojects geometries to local equal-area/UTM CRS for accurate distance and area calculations.
    - Stores file metadata and per-feature measurements in the database.
    """
    filename = file.filename or ""
    
    # 1. Validate file extension early
    try:
        ext = FileIngestionService.validate_file_extension(filename)
    except InvalidFileFormatException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    # 2. Read file content
    content = await file.read()
    file_size = len(content)

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes).",
        )

    file_type = "kml" if ext == ".kml" else "shapefile_zip"

    # 3. Create initial FileRecord in DB with PENDING status
    file_record = FileRecord(
        filename=filename,
        file_size=file_size,
        file_type=file_type,
        status=FileStatus.PENDING.value,
    )
    db.add(file_record)
    await db.flush()

    # 4. Process file and transition status: PROCESSING -> COMPLETED/FAILED
    try:
        file_record.status = FileStatus.PROCESSING.value
        await db.flush()

        # Parse upload into GeoDataFrame and raw CRS string
        gdf, raw_crs_str = FileIngestionService.process_upload(filename, content)

        # Normalize source CRS
        source_crs = CRSProjectorService.normalize_source_crs(gdf.crs)
        source_crs_str = source_crs.to_string()

        feature_measurements = []
        for idx, row in gdf.iterrows():
            geometry = row.geometry if hasattr(row, "geometry") else None
            geom_type = geometry.geom_type if geometry is not None else "Unknown"

            properties = MeasurementEngineService.sanitize_properties(row)
            source_feature_id = str(properties.get("id") or properties.get("ID") or idx)

            if geometry is not None and not geometry.is_empty:
                # Dynamic Reprojection to Local UTM / Equal Area CRS
                projected_geom, projected_crs_used = CRSProjectorService.reproject_to_projected_crs(
                    geometry, source_crs
                )

                # Compute Measurements (Area / Length)
                (
                    m_status,
                    area_m2,
                    area_ha,
                    len_m,
                    len_km,
                    err_msg,
                ) = MeasurementEngineService.measure_geometry(projected_geom)
            else:
                projected_crs_used = source_crs_str
                (
                    m_status,
                    area_m2,
                    area_ha,
                    len_m,
                    len_km,
                    err_msg,
                ) = (
                    "UNSUPPORTED_GEOMETRY",
                    None,
                    None,
                    None,
                    None,
                    "Geometry is empty or missing",
                )

            fm = FeatureMeasurement(
                file_id=file_record.id,
                feature_index=int(idx),
                source_feature_id=source_feature_id,
                geometry_type=geom_type,
                properties_json=json.dumps(properties),
                source_crs=source_crs_str,
                projected_crs_used=projected_crs_used,
                measurement_status=m_status if isinstance(m_status, str) else m_status.value,
                area_sq_meters=area_m2,
                area_hectares=area_ha,
                length_meters=len_m,
                length_km=len_km,
                error_message=err_msg,
            )
            feature_measurements.append(fm)

        db.add_all(feature_measurements)
        file_record.status = FileStatus.COMPLETED.value
        file_record.feature_count = len(feature_measurements)
        file_record.detected_crs = source_crs_str
        await db.commit()

        return FileUploadResponse(
            id=file_record.id,
            filename=file_record.filename,
            status=file_record.status,
            feature_count=file_record.feature_count,
            crs=file_record.detected_crs,
        )

    except GeospatialAPIException as exc:
        file_record.status = FileStatus.FAILED.value
        file_record.error_message = exc.message
        await db.commit()
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    except Exception as exc:
        logger.error(f"Unhandled processing error for file '{filename}': {exc}", exc_info=True)
        file_record.status = FileStatus.FAILED.value
        file_record.error_message = str(exc)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to process geospatial file: {str(exc)}",
        )


@router.get(
    "/{id}/",
    response_model=FileDetailResponse,
    summary="Get file metadata and processing status",
)
async def get_file_details(
    id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve metadata and status for a previously uploaded file."""
    stmt = select(FileRecord).where(FileRecord.id == id)
    result = await db.execute(stmt)
    file_record = result.scalar_one_or_none()

    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File record with ID '{id}' not found.",
        )

    return FileDetailResponse.model_validate(file_record)


@router.get(
    "/{id}/measurements/",
    response_model=PaginatedFeatureMeasurementsResponse,
    summary="Get paginated feature measurements for a file",
)
async def get_file_measurements(
    id: str,
    page: int = Query(1, ge=1, description="Page number (starts at 1)"),
    page_size: int = Query(50, ge=1, le=500, description="Items per page (max 500)"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve paginated feature measurement records for a specific uploaded file."""
    # Check if file exists
    stmt_file = select(FileRecord).where(FileRecord.id == id)
    res_file = await db.execute(stmt_file)
    file_record = res_file.scalar_one_or_none()

    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File record with ID '{id}' not found.",
        )

    # Count total features
    stmt_count = select(func.count()).select_from(FeatureMeasurement).where(FeatureMeasurement.file_id == id)
    res_count = await db.execute(stmt_count)
    total_items = res_count.scalar() or 0

    # Fetch paginated items
    offset = (page - 1) * page_size
    stmt_items = (
        select(FeatureMeasurement)
        .where(FeatureMeasurement.file_id == id)
        .order_by(FeatureMeasurement.feature_index)
        .offset(offset)
        .limit(page_size)
    )
    res_items = await db.execute(stmt_items)
    items_raw = res_items.scalars().all()

    items_response = []
    for item in items_raw:
        props = json.loads(item.properties_json) if item.properties_json else {}
        m_detail = MeasurementDetail(
            area_sq_meters=item.area_sq_meters,
            area_hectares=item.area_hectares,
            length_meters=item.length_meters,
            length_km=item.length_km,
        )
        fm_res = FeatureMeasurementResponse(
            feature_id=item.source_feature_id or str(item.feature_index),
            geometry_type=item.geometry_type,
            properties=props,
            source_crs=item.source_crs,
            projected_crs_used=item.projected_crs_used,
            measurement_status=item.measurement_status,
            measurements=m_detail,
            error_message=item.error_message,
        )
        items_response.append(fm_res)

    total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 0

    return PaginatedFeatureMeasurementsResponse(
        file_id=id,
        total=total_items,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=items_response,
    )
