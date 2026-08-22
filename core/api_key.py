class APIKey:
    def __init__(self, key: str) -> None:
        self.set_key(key)

    def get_key(self) -> str:
        return self.__key

    def set_key(self, new_key: str) -> None:
        if not isinstance(new_key, str):
            raise ValueError("API key must be a string.")
        if not new_key.strip():
            raise ValueError("API key cannot be empty or whitespace.")
        self.__key = new_key
        self.__usable = True
        self.__next_retry_time: float = 0.0

    def set_usable(self, usable: bool) -> None:
        if not isinstance(usable, bool):
            raise ValueError("Usable flag must be a boolean.")
        self.__usable = usable

    def get_usable(self) -> bool:
        return self.__usable

    def set_retry_time(self, retry_time: float | None) -> None:
        if retry_time is not None and not isinstance(retry_time, (int, float)):
            raise ValueError("Retry time must be a float.")
        if retry_time is None:
            self.__next_retry_time = 0.0
        else:
            self.__next_retry_time = retry_time

    def get_retry_time(self) -> float:
        return self.__next_retry_time

    def __repr__(self) -> str:
        return f"APIKey(usable={self.__usable})"
