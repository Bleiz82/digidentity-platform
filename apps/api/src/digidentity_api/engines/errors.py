class ProviderError(Exception):
    def __init__(self, *, status: int, provider: str, message: str = "") -> None:
        self.status = status
        self.provider = provider
        self.message = message
        super().__init__(f"provider={provider} status={status} {message}")


class CircuitOpenError(Exception):
    def __init__(self, model: str) -> None:
        self.model = model
        super().__init__(f"circuit breaker open for model={model}")
