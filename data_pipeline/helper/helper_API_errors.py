class DataPipelineError(Exception):
    """Base class for backfill-related failures."""

class APITimeoutError(DataPipelineError):
    """Network timeout calling the GeoMet API."""

class APIConnectError(DataPipelineError):
    """Error connecting to network entirely."""

class APIStatusError(DataPipelineError):
    """API response returned a bad status-code."""

class APIResponseError(DataPipelineError):
    """API responded, but the payload was malformed or unexpected."""

class APIZeroCountError(DataPipelineError):
    """API responded, but return 0 results"""

class APICountMismatchError(DataPipelineError):
    """API responded, but we have inconsistency between expected results and actual results"""

class DataUniquenessConstraintViolation(DataPipelineError):
    """Our data has a column that's supposed to be unique - but isn't."""

class DBError(DataPipelineError):
    """DB write failed (constraint violation, connection issue, etc.)."""