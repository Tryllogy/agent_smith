import time


class APIKey:
    """An API key and its rotation state.

    Tracks whether the key is still usable and how long to wait
    before retrying it. repr() never shows the key.
    """

    def __init__(self, key: str) -> None:
        """Wrap key; raise ValueError if it is blank."""
        self.set_key(key)

    def get_key(self) -> str:
        """Return the raw key."""
        return self.__key

    def set_key(self, new_key: str) -> None:
        """Replace the key and reset its state; raise ValueError if blank."""
        if not isinstance(new_key, str):
            raise ValueError("API key must be a string.")
        if not new_key.strip():
            raise ValueError("API key cannot be empty or whitespace.")
        self.__key = new_key
        self.__usable = True
        self.__next_retry_time: float = 0.0
        self.__token_budget: tuple[int, int, float] | None = None

    def set_usable(self, usable: bool) -> None:
        """Mark the key as usable or exhausted."""
        if not isinstance(usable, bool):
            raise ValueError("Usable flag must be a boolean.")
        self.__usable = usable

    def get_usable(self) -> bool:
        """Return whether the key can still be used."""
        return self.__usable

    def set_retry_time(self, retry_time: float | None) -> None:
        """Set the wait in seconds before a retry; None resets it to 0."""
        if retry_time is not None and not isinstance(retry_time, (int, float)):
            raise ValueError("Retry time must be a float.")
        if retry_time is None:
            self.__next_retry_time = 0.0
        else:
            self.__next_retry_time = retry_time

    def get_retry_time(self) -> float:
        """Return the wait in seconds before the key may be retried."""
        return self.__next_retry_time

    def set_token_budget(self, limit: int, remaining: int) -> None:
        """Record the provider's token limit and what is left, as of now."""
        self.__token_budget = (limit, remaining, time.time())

    def get_token_budget(self) -> tuple[int, int, float] | None:
        """Return (limit, remaining, time observed), or None if unknown."""
        return self.__token_budget

    def __repr__(self) -> str:
        """Show the state only, never the key."""
        return f"APIKey(usable={self.__usable})"
