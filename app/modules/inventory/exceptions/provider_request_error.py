class ProviderRequestError(Exception):
    def __init__(self, message: str, is_timeout: bool = False):
        self.message = message
        self.is_timeout = is_timeout
        super().__init__(message)