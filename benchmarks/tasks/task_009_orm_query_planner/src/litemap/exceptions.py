"""Custom exceptions for litemap."""


class LitemapError(Exception):
    """Base exception."""


class QueryError(LitemapError):
    """Raised when query construction or execution fails."""


class SchemaError(LitemapError):
    """Raised on schema / migration issues."""
