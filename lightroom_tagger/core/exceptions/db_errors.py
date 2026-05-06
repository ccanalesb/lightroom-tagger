"""Database-layer domain errors."""


class StackMutationError(ValueError):
    """Invalid stack edit; ``status_code`` is intended for HTTP error mapping."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code
