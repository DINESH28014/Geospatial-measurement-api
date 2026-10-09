import os
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_upload_kml_file_success(client: AsyncClient, sample_data_dir: str):
    kml_path = os.path.join(sample_data_dir, "sample_polygon.kml")
    with open(kml_path, "rb") as f:
        file_bytes = f.read()

    files = {"file": ("sample_polygon.kml", file_bytes, "application/vnd.google-earth.kml+xml")}
    response = await client.post("/api/files/", files=files)

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["filename"] == "sample_polygon.kml"
    assert data["status"] == "COMPLETED"
    assert data["feature_count"] == 1
    assert data["crs"] is not None

    file_id = data["id"]

    # Retrieve file details
    detail_res = await client.get(f"/api/files/{file_id}/")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["id"] == file_id
    assert detail_data["status"] == "COMPLETED"
    assert detail_data["feature_count"] == 1

    # Retrieve feature measurements
    meas_res = await client.get(f"/api/files/{file_id}/measurements/")
    assert meas_res.status_code == 200
    meas_data = meas_res.json()
    assert meas_data["file_id"] == file_id
    assert meas_data["total"] == 1
    assert len(meas_data["items"]) == 1

    feature = meas_data["items"][0]
    assert feature["geometry_type"] == "Polygon"
    assert feature["measurement_status"] == "COMPLETED"
    assert feature["measurements"]["area_sq_meters"] > 0
    assert feature["measurements"]["area_hectares"] > 0


@pytest.mark.asyncio
async def test_upload_shapefile_zip_success(client: AsyncClient, sample_data_dir: str):
    zip_path = os.path.join(sample_data_dir, "sample_shapefile.zip")
    with open(zip_path, "rb") as f:
        file_bytes = f.read()

    files = {"file": ("sample_shapefile.zip", file_bytes, "application/zip")}
    response = await client.post("/api/files/", files=files)

    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "sample_shapefile.zip"
    assert data["status"] == "COMPLETED"
    assert data["feature_count"] == 2

    file_id = data["id"]

    # Test pagination
    meas_res = await client.get(f"/api/files/{file_id}/measurements/?page=1&page_size=1")
    assert meas_res.status_code == 200
    meas_data = meas_res.json()
    assert meas_data["total"] == 2
    assert meas_data["page"] == 1
    assert meas_data["page_size"] == 1
    assert len(meas_data["items"]) == 1


@pytest.mark.asyncio
async def test_upload_invalid_extension(client: AsyncClient):
    files = {"file": ("invalid.txt", b"some text content", "text/plain")}
    response = await client.post("/api/files/", files=files)

    assert response.status_code == 400
    data = response.json()
    assert "Unsupported file extension" in data["detail"]


@pytest.mark.asyncio
async def test_upload_empty_file(client: AsyncClient):
    files = {"file": ("empty.kml", b"", "application/vnd.google-earth.kml+xml")}
    response = await client.post("/api/files/", files=files)

    assert response.status_code == 400
    data = response.json()
    assert "empty" in data["detail"].lower()


@pytest.mark.asyncio
async def test_get_non_existent_file(client: AsyncClient):
    fake_id = "00000000-0000-0000-0000-000000000000"
    res = await client.get(f"/api/files/{fake_id}/")
    assert res.status_code == 404

    res_meas = await client.get(f"/api/files/{fake_id}/measurements/")
    assert res_meas.status_code == 404
