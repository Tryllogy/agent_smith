import calendar
import time
from datetime import datetime

from httpx import Headers

from core.validators import ProviderConfig


class Provider:
    def __init__(self, provider_config: ProviderConfig) -> None:
        self.config: ProviderConfig = provider_config

    def get_retry_after(self, headers: Headers) -> float | None:
        retry_after_value: float | None = None
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
                    return self.convert_from_epoch_to_delay(
                        retry_after_date
                    )
        return None

    def convert_from_epoch_to_delay(
        self, retry_after_value: str | float, scale: int = 1
    ) -> float:
        return float(retry_after_value) / scale - time.time()

    def check_if_date_format(self, date_str: str) -> bool:
        try:
            datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S GMT")
            return True
        except ValueError:
            return False

    def get_message(self, data: dict) -> dict:
        message = self.config.message
        if message not in data:
            raise ValueError(f"Message key '{message}' not found in data")
        return data[message][0].get("message")
