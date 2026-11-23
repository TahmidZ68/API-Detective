"""Custom exception hierarchy for API Detective."""

from __future__ import annotations


class APIDetectiveError(Exception):
    """Base exception for all API Detective errors."""

    def __init__(self, message: str, code: str = "INTERNAL_ERROR", details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class SSRFProtectionError(APIDetectiveError):
    """Raised when an outgoing HTTP request violates SSRF security policy."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message=message, code="SSRF_BLOCKED", details=details)


class SpecificationParseError(APIDetectiveError):
    """Raised when an OpenAPI or JSON Schema specification cannot be parsed."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message=message, code="SPEC_PARSE_ERROR", details=details)


class RepositoryAccessError(APIDetectiveError):
    """Raised when a repository path is invalid, outside allowed roots, or unreadable."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message=message, code="REPO_ACCESS_ERROR", details=details)


class RepairApprovalRequiredError(APIDetectiveError):
    """Raised when an operation attempts to modify code without explicit approval."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message=message, code="APPROVAL_REQUIRED", details=details)


class ForbiddenRepairError(APIDetectiveError):
    """Raised when a proposed repair attempts a forbidden unsafe modification."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message=message, code="FORBIDDEN_REPAIR", details=details)


class ToolExecutionTimeoutError(APIDetectiveError):
    """Raised when an agent tool exceeds its configured execution timeout."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message=message, code="TOOL_TIMEOUT", details=details)
