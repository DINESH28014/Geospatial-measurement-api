import os
import tempfile
import zipfile
import geopandas as gpd
from shapely.geometry import Polygon, LineString, Point

def generate_sample_shapefile_zip(output_zip_path: str):
    # Create sample features
    poly1 = Polygon([(-73.98, 40.76), (-73.95, 40.80), (-73.94, 40.79), (-73.97, 40.76), (-73.98, 40.76)])
    poly2 = Polygon([(-73.90, 40.70), (-73.88, 40.72), (-73.87, 40.71), (-73.90, 40.70)])
    
    gdf = gpd.GeoDataFrame(
        {
            "id": [1, 2],
            "name": ["Parcel A", "Parcel B"],
            "type": ["Farm", "Forest"],
        },
        geometry=[poly1, poly2],
        crs="EPSG:4326"
    )
    
    with tempfile.TemporaryDirectory() as tmpdir:
        shp_path = os.path.join(tmpdir, "sample_parcels.shp")
        gdf.to_file(shp_path, driver="ESRI Shapefile")
        
        with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for ext in [".shp", ".shx", ".dbf", ".prj"]:
                fpath = os.path.join(tmpdir, f"sample_parcels{ext}")
                if os.path.exists(fpath):
                    zf.write(fpath, arcname=f"sample_parcels{ext}")
                    
    print(f"Successfully generated sample shapefile zip at: {output_zip_path}")

if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(__file__), "sample_data")
    os.makedirs(out_dir, exist_ok=True)
    generate_sample_shapefile_zip(os.path.join(out_dir, "sample_shapefile.zip"))
