from core.config_models import LLMResponse
from core.llm.client import LLMClient


class FallbackClient:
    """LLM clients tried in order: the requested one, then the fallbacks.

    Every request goes to the client in use. fall_back() moves to the
    next one for the rest of the task, never back. url and model_name
    follow the client in use, so each step reports the endpoint that
    really answered it.
    """

    def __init__(self, clients: list[LLMClient]) -> None:
        """Start on clients[0]; raise ValueError if clients is empty."""
        if not clients:
            raise ValueError("FallbackClient needs at least one client.")
        self.clients: list[LLMClient] = clients
        self.index: int = 0

    @property
    def current(self) -> LLMClient:
        """Return the client in use."""
        return self.clients[self.index]

    @property
    def url(self) -> str:
        """Return the full endpoint of the client in use."""
        return self.current.url

    @property
    def model_name(self) -> str:
        """Return the model of the client in use."""
        return self.current.model_name

    def get_llm_reponse(
        self,
        timeout_max: float,
        messages: list,
        max_tokens: int,
    ) -> LLMResponse:
        """Send the request to the client in use; its errors propagate."""
        return self.current.get_llm_reponse(
            timeout_max=timeout_max,
            messages=messages,
            max_tokens=max_tokens,
        )

    def fall_back(self) -> bool:
        """Switch to the next client; return False when none is left."""
        if self.index + 1 >= len(self.clients):
            return False
        self.index += 1
        return True
