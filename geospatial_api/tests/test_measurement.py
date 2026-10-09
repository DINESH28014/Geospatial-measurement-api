import pytest
from shapely.geometry import Polygon, LineString, Point, GeometryCollection

from app.models.file_record import MeasurementStatus
from app.services.measurement_engine import MeasurementEngineService


def test_polygon_measurement():
    # 100m x 100m square polygon in projected metric space
    square_poly = Polygon([(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)])

    (
        status,
        area_m2,
        area_ha,
        len_m,
        len_km,
        err,
    ) = MeasurementEngineService.measure_geometry(square_poly)

    assert status == MeasurementStatus.COMPLETED
    assert area_m2 == 10000.0
    assert area_ha == 1.0
    assert len_m == 400.0
    assert len_km == 0.4
    assert err is None


def test_linestring_measurement():
    # 1500m LineString in projected metric space
    line = LineString([(0, 0), (1000, 0), (1000, 500)])

    (
        status,
        area_m2,
        area_ha,
        len_m,
        len_km,
        err,
    ) = MeasurementEngineService.measure_geometry(line)

    assert status == MeasurementStatus.COMPLETED
    assert area_m2 is None
    assert area_ha is None
    assert len_m == 1500.0
    assert len_km == 1.5
    assert err is None


def test_point_measurement():
    pt = Point(50, 50)

    (
        status,
        area_m2,
        area_ha,
        len_m,
        len_km,
        err,
    ) = MeasurementEngineService.measure_geometry(pt)

    assert status == MeasurementStatus.MEASUREMENT_NOT_APPLICABLE
    assert area_m2 is None
    assert len_m is None
    assert "Points do not possess" in err


def test_unsupported_geometry():
    empty_poly = Polygon()

    (
        status,
        area_m2,
        area_ha,
        len_m,
        len_km,
        err,
    ) = MeasurementEngineService.measure_geometry(empty_poly)

    assert status == MeasurementStatus.UNSUPPORTED_GEOMETRY
    assert area_m2 is None
    assert len_m is None
