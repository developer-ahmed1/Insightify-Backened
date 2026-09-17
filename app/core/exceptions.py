"""
Custom exceptions and error handling for the application.
"""
from typing import Any, Dict, Optional


class InsightyifyException(Exception):
    """Base exception for all application errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or "INTERNAL_ERROR"
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API response."""
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details,
        }


# Authentication Errors
class AuthenticationError(InsightyifyException):
    """Authentication failed."""

    def __init__(self, message: str = "Authentication failed", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            status_code=401,
            error_code="AUTHENTICATION_ERROR",
            details=details,
        )


class TokenExpiredError(AuthenticationError):
    """Token has expired."""

    def __init__(self):
        super().__init__(
            message="Token has expired",
            details={"action": "refresh_token"},
        )
        self.error_code = "TOKEN_EXPIRED"


class InvalidTokenError(AuthenticationError):
    """Token is invalid."""

    def __init__(self):
        super().__init__(
            message="Invalid authentication token",
        )
        self.error_code = "INVALID_TOKEN"


# Authorization Errors
class ForbiddenError(InsightyifyException):
    """Access denied."""

    def __init__(
        self,
        message: str = "Access denied",
        feature: Optional[str] = None,
    ):
        details = {}
        if feature:
            details["feature"] = feature
            details["upgrade_url"] = "/api/v1/subscriptions/plans"
        super().__init__(
            message=message,
            status_code=403,
            error_code="FORBIDDEN",
            details=details,
        )


class PremiumRequiredError(ForbiddenError):
    """Premium subscription required."""

    def __init__(self, feature: str):
        super().__init__(
            message=f"Premium subscription required for {feature}",
            feature=feature,
        )
        self.error_code = "PREMIUM_REQUIRED"


# Rate Limiting Errors
class RateLimitExceededError(InsightyifyException):
    """Rate limit exceeded."""

    def __init__(
        self,
        action: str,
        limit: int,
        reset_at: Optional[str] = None,
    ):
        super().__init__(
            message=f"Rate limit exceeded for {action}",
            status_code=429,
            error_code="RATE_LIMIT_EXCEEDED",
            details={
                "action": action,
                "limit": limit,
                "remaining": 0,
                "reset_at": reset_at or "midnight UTC",
            },
        )


# Resource Errors
class NotFoundError(InsightyifyException):
    """Resource not found."""

    def __init__(self, resource: str, identifier: Optional[str] = None):
        message = f"{resource} not found"
        if identifier:
            message = f"{resource} with id '{identifier}' not found"
        super().__init__(
            message=message,
            status_code=404,
            error_code="NOT_FOUND",
            details={"resource": resource},
        )


class AlreadyExistsError(InsightyifyException):
    """Resource already exists."""

    def __init__(self, resource: str, field: str, value: str):
        super().__init__(
            message=f"{resource} with {field} '{value}' already exists",
            status_code=409,
            error_code="ALREADY_EXISTS",
            details={"resource": resource, "field": field},
        )


# Validation Errors
class ValidationError(InsightyifyException):
    """Validation failed."""

    def __init__(self, message: str, field: Optional[str] = None):
        details = {}
        if field:
            details["field"] = field
        super().__init__(
            message=message,
            status_code=422,
            error_code="VALIDATION_ERROR",
            details=details,
        )


class FileTooLargeError(ValidationError):
    """File size exceeds limit."""

    def __init__(self, max_size_mb: int):
        super().__init__(
            message=f"File size exceeds maximum of {max_size_mb}MB",
            field="file",
        )
        self.error_code = "FILE_TOO_LARGE"


class UnsupportedMediaTypeError(ValidationError):
    """Unsupported media type."""

    def __init__(self, content_type: str, allowed_types: list):
        super().__init__(
            message=f"Unsupported media type: {content_type}",
            field="content_type",
        )
        self.error_code = "UNSUPPORTED_MEDIA_TYPE"
        self.details["allowed_types"] = allowed_types


# External Service Errors
class ExternalServiceError(InsightyifyException):
    """External service failed."""

    def __init__(self, service: str, message: str = "External service error"):
        super().__init__(
            message=f"{service}: {message}",
            status_code=503,
            error_code="EXTERNAL_SERVICE_ERROR",
            details={"service": service},
        )


class AIServiceError(ExternalServiceError):
    """AI service failed."""

    def __init__(self, message: str = "AI analysis failed"):
        super().__init__(service="AI", message=message)
        self.error_code = "AI_SERVICE_ERROR"


class StorageServiceError(ExternalServiceError):
    """Storage service failed."""

    def __init__(self, message: str = "Storage operation failed"):
        super().__init__(service="Storage", message=message)
        self.error_code = "STORAGE_SERVICE_ERROR"
