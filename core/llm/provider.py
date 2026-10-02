import calendar
import time
from datetime import datetime

from httpx import Headers

from core.config_models import ProviderConfig


class Provider:
    """Reads a provider's response through its ProviderConfig names."""

    def __init__(self, provider_config: ProviderConfig) -> None:
        """Keep the provider configuration."""
        self.config: ProviderConfig = provider_config

    def convert_from_epoch_to_delay(
        self, retry_after_value: str | float, scale: int = 1
    ) -> float:
        """Convert an epoch (divided by scale) to seconds from now."""
        return float(retry_after_value) / scale - time.time()

    def check_if_date_format(self, date_str: str) -> bool:
        """Return True if date_str is an HTTP date (IMF-fixdate)."""
        try:
            datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S GMT")
            return True
        except ValueError:
            return False

    def get_token_rate(self, headers: Headers) -> tuple[int, int] | None:
        """Return the (limit, remaining) tokens of the current window.

        Read from the headers named in token_rate_limit; None when the
        provider declares none or a header is missing or not a number.
        """
        config = self.config.token_rate_limit
        if config is None:
            return None
        limit = headers.get(config.limit)
        remaining = headers.get(config.remaining)
        if limit is None or remaining is None:
            return None
        if not str(limit).isdigit() or not str(remaining).isdigit():
            return None
        return int(limit), int(remaining)

    def get_retry_after(self, headers: Headers) -> float | None:
        """Return the wait in seconds from the rate-limit headers.

        Uses the first configured header that parses; None otherwise.
        """
        retry_after_value: str | float | None = None
        provider_retry_after = self.config.retry_after
        for name, config in provider_retry_after.names.items():
            if name in headers:
                retry_after_value = headers[name]
                if "epoch" in config.format and retry_after_value.isdigit():
                    return self.convert_from_epoch_to_delay(
                        retry_after_value, config.scale
                    )
                elif (
                    "duration" in config.format and retry_after_value.isdigit()
                ):
                    return float(retry_after_value) / config.scale
                elif "date" in config.format and self.check_if_date_format(
                    retry_after_value
                ):
                    retry_after_date = datetime.strptime(
                        retry_after_value, "%a, %d %b %Y %H:%M:%S GMT"
                    )
                    retry_after_date = calendar.timegm(
                        retry_after_date.utctimetuple()
                    )
                    return self.convert_from_epoch_to_delay(retry_after_date)
        return None

    def get_choice(self, data: dict) -> dict | None:
        """Return the first choice, or None."""
        choice_key = self.config.choice
        if choice_key not in data:
            return None
        return data[choice_key][0] if data[choice_key] else None

    def get_message(self, data: dict) -> dict | None:
        """Return the message of the first choice, or None."""
        choice = self.get_choice(data)
        if choice is None:
            return None
        return choice.get(self.config.message, None)

    def get_finish_reason(self, data: dict) -> str | None:
        """Return the finish reason of the first choice, or None."""
        choice = self.get_choice(data)
        if choice is None:
            return None
        return choice.get(self.config.finish_reason, "")

    def get_usage(self, data: dict) -> dict | None:
        """Return the usage block, or None."""
        usage_key = self.config.usage
        if usage_key not in data:
            return None
        return data[usage_key]

    def get_content(self, data: dict) -> str:
        """Return the message content, or "" without a message."""
        message = self.get_message(data)
        if message is None:
            return ""
        content = message.get(self.config.content, "")
        return content

    def get_model(self, data: dict) -> str:
        """Return the model reported, or ""."""
        model_key = self.config.model
        if model_key not in data:
            return ""
        return data[model_key]

    def get_error(self, data: dict) -> dict:
        """Return the provider's error block, or {}."""
        error_key = self.config.error
        if error_key not in data:
            return {}
        return data[error_key]

    def get_reasoning(self, data: dict) -> str:
        """Return the reasoning text, or ""."""
        choice = self.get_message(data)
        if choice is None:
            return ""
        reasoning_data = choice.get(self.config.reasoning)
        if reasoning_data is None:
            return ""
        return reasoning_data

    def get_input_tokens(self, data: dict) -> int:
        """Return the prompt token count, or 0 if absent."""
        usage = self.get_usage(data)
        if usage is None:
            return 0
        input_tokens_key = self.config.input_tokens
        if input_tokens_key not in usage:
            return 0
        return usage.get(input_tokens_key, 0)

    def get_output_tokens(self, data: dict) -> int:
        """Return the completion token count, or 0 if absent."""
        usage = self.get_usage(data)
        if usage is None:
            return 0
        output_tokens_key = self.config.output_tokens
        if output_tokens_key not in usage:
            return 0
        return usage.get(output_tokens_key, 0)
