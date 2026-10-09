import os
from typing import Set
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Geospatial File Measurement API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./geospatial.db")
    
    # File processing
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: Set[str] = {".kml", ".zip"}
    
    # Projection defaults
    DEFAULT_FALLBACK_CRS: str = "EPSG:4326"
    
    model_config = SettingsConfigDict(case_sensitive=True)

settings = Settings()
