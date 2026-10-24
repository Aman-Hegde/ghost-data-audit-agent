"""Domain-specific, actionable errors."""


class AuditAgentError(Exception):
    """Base class for expected audit-agent failures."""


class DataValidationError(AuditAgentError):
    """Raised when participant data violates an input contract."""


class EvidenceParseError(AuditAgentError):
    """Raised when a manifested evidence artifact cannot be parsed safely."""
