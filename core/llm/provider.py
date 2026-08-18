from core.validators import ProviderConfig


class Provider:
    def __init__(
        self,
        url: str,
        endpoint: str,
        header: dict,
        api_key_env_var: str,
        reasoning_name: str,
        retry_after: dict[str, dict[str, list[str]]]
    ) -> None:
        self.url: str = url
        self.endpoint: str = endpoint
        self.header: dict = header
        self.api_key_env_var: str = api_key_env_var
        self.reasoning_name: str = reasoning_name
        self.retry_after: dict = retry_after

    @classmethod
    def from_config(
        cls,
        provider_config: ProviderConfig
    ) -> ProviderConfig:
        return cls(
            url=provider_config.url,
            endpoint=provider_config.endpoint,
            header=provider_config.header,
            api_key_env_var=provider_config.api_key_env_var,
            reasoning_name=provider_config.reasoning_name,
            retry_after=provider_config.retry_after,
        )
