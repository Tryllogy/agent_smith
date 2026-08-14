ERRORS_TRANSIENT = {408, 409, 429} | {
    status_code for status_code in range(500, 600)
}

ERRORS_PERMANENT = {
    400,
    401,
    403,
    404,
}


class LLMResponseError(Exception):
    """
    Represents an error response from the LLM provider.
    This error indicates that the request to the LLM provider failed
    due to various reasons, such as invalid input, server issues, or
    other unexpected conditions.
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class TransientLLMResponseError(LLMResponseError):
    """
    Represents a transient error response from the LLM provider.
    This error indicates that the request may succeed if retried after
    a certain period.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, status_code)
        self.retry_after: float | None = retry_after


class PermanentLLMResponseError(LLMResponseError):
    """
    Represents a permanent error response from the LLM provider.
    This error indicates that the request is invalid or cannot be processed,
    and retrying will not resolve the issue.
    """

    pass
