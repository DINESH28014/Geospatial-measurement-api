import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.core.database import Base


class FileStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class MeasurementStatus(str, enum.Enum):
    COMPLETED = "COMPLETED"
    MEASUREMENT_NOT_APPLICABLE = "MEASUREMENT_NOT_APPLICABLE"
    UNSUPPORTED_GEOMETRY = "UNSUPPORTED_GEOMETRY"
    FAILED = "FAILED"


def utc_now():
    return datetime.now(timezone.utc)


class FileRecord(Base):
    __tablename__ = "file_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_type = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False, default=FileStatus.PENDING.value)
    error_message = Column(Text, nullable=True)
    feature_count = Column(Integer, default=0)
    detected_crs = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    measurements = relationship(
        "FeatureMeasurement",
        back_populates="file",
        cascade="all, delete-orphan",
        order_by="FeatureMeasurement.feature_index",
    )


class FeatureMeasurement(Base):
    __tablename__ = "feature_measurements"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id = Column(String(36), ForeignKey("file_records.id", ondelete="CASCADE"), nullable=False, index=True)
    feature_index = Column(Integer, nullable=False)
    source_feature_id = Column(String(255), nullable=True)
    geometry_type = Column(String(50), nullable=False)
    properties_json = Column(Text, nullable=True)
    source_crs = Column(String(100), nullable=True)
    projected_crs_used = Column(String(100), nullable=True)
    measurement_status = Column(String(50), nullable=False, default=MeasurementStatus.COMPLETED.value)
    area_sq_meters = Column(Float, nullable=True)
    area_hectares = Column(Float, nullable=True)
    length_meters = Column(Float, nullable=True)
    length_km = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    file = relationship("FileRecord", back_populates="measurements")
