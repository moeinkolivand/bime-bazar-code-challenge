from abc import ABC, abstractmethod

from app.modules.inventory.dtoes.dtos import ProviderResponse


class IGetRequest(ABC):

    @abstractmethod
    def get(
        self, path: str, params: dict | None = None, headers: dict | None = None
    ) -> ProviderResponse: ...


class IPostRequest(ABC):

    @abstractmethod
    def post(
        self,
        path: str,
        json: dict | None = None,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> ProviderResponse: ...
