class ProviderRequestError(Exception):
    """Raised by transports (REST/SOAP/gRPC) on network failure, timeout, or non-2xx response."""

    def __init__(self, message: str, is_timeout: bool = False):
        self.message = message
        self.is_timeout = is_timeout
        super().__init__(message)


class UnknownProviderKeyError(Exception):
    """Raised when ProviderRegistry has no client class registered for a provider's key."""

    def __init__(self, key: str):
        self.key = key
        super().__init__(f"No provider client registered for key '{key}'")


class ProviderMisconfiguredError(Exception):
    """
    Raised when a provider's declared capabilities (from the DB / InventoryProvider.capabilities)
    disagree with what its concrete client class actually implements. This should never happen
    in a correctly configured system — it signals either a bad DB seed/migration or a client
    class that was implemented incorrectly. Raised loudly and immediately at client-build time,
    rather than surfacing later as a silent isinstance() mismatch deep in ProviderService.
    """

    def __init__(self, provider_name: str, detail: str):
        self.provider_name = provider_name
        self.detail = detail
        super().__init__(f"Provider '{provider_name}' is misconfigured: {detail}")