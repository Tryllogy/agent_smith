class APIKey:
    def __init__(
        self,
        key: str
    ) -> None:
        self.set_key(key)

    def get_key(self) -> str:
        return self.__key

    def set_key(
        self,
        new_key: str
    ) -> None:
        if not isinstance(new_key, str):
            raise ValueError("API key must be a string.")
        if not new_key.strip():
            raise ValueError("API key cannot be empty or whitespace.")
        self.__key = new_key
        self.__usable = True

    def set_usable(
        self,
        usable: bool
    ) -> None:
        if not isinstance(usable, bool):
            raise ValueError("Usable flag must be a boolean.")
        self.__usable = usable

    def get_usable(self) -> bool:
        return self.__usable

    def __repr__(self) -> str:
        return f"APIKey(usable={self.__usable})"
