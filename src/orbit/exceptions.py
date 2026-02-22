"""Orbit SDK exception hierarchy."""

from __future__ import annotations


class OrbitError(Exception):
    """Base SDK exception."""


class OrbitAuthError(OrbitError):
    """Authentication failed."""


class OrbitValidationError(OrbitError):
    """Request validation failed."""


class OrbitRateLimitError(OrbitError):
    """Request was rate limited."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class OrbitNotFoundError(OrbitError):
    """Requested resource was not found."""


class OrbitServerError(OrbitError):
    """Server-side failure."""


class OrbitTimeoutError(OrbitError):
    """Request timed out."""
