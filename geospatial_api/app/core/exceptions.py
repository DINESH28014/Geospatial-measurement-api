class GeospatialAPIException(Exception):
    """Base exception for Geospatial API."""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class InvalidFileFormatException(GeospatialAPIException):
    """Raised when uploaded file extension or format is unsupported."""
    def __init__(self, message: str = "Invalid file format or extension."):
        super().__init__(message, status_code=400)


class SecurityValidationException(GeospatialAPIException):
    """Raised when a security check fails (e.g., path traversal / Zip Slip)."""
    def __init__(self, message: str = "Security validation failed for the uploaded archive."):
        super().__init__(message, status_code=400)


class CorruptedFileException(GeospatialAPIException):
    """Raised when file parsing fails due to corruption or missing companion files."""
    def __init__(self, message: str = "Corrupted geospatial file or missing shapefile components."):
        super().__init__(message, status_code=422)


class FeatureProcessingException(GeospatialAPIException):
    """Raised when processing feature geometries fails."""
    def __init__(self, message: str = "Failed to process geospatial feature."):
        super().__init__(message, status_code=422)
