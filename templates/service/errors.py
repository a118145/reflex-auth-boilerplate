"""How the service refuses. Both messages are written for the user."""


class PermissionDeniedError(Exception):
    """The actor may not do this. The message is safe to show."""


class DomainError(ValueError):
    """The request breaks a rule (not a permission). The message is safe to show."""
