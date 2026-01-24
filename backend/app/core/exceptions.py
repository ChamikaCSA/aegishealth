"""
Custom exceptions for AegisHealth backend.

Maps domain errors to HTTP status codes for consistent API responses.
"""

from __future__ import annotations


class AegisHealthException(Exception):
    """Base exception for AegisHealth backend."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class JobNotFoundError(AegisHealthException):
    """Raised when a training job is not found."""

    def __init__(self, job_id: int):
        super().__init__(f"Job {job_id} not found", status_code=404)


class ClientRegistrationError(AegisHealthException):
    """Raised when client registration fails."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message, status_code=status_code)


class UnauthorizedError(AegisHealthException):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Invalid or expired token"):
        super().__init__(message, status_code=401)


class ForbiddenError(AegisHealthException):
    """Raised when user lacks permission."""

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, status_code=403)
