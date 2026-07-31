from abc import abstractmethod, ABC
from typing import Optional


class IProviderAuthentication(ABC):
    @abstractmethod
    def authentcate() -> Optional[str]: ...
