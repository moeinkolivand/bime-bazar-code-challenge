import httpx

from app.modules.inventory.dtoes.dtos import ProviderResponse, RequestSpec
from app.modules.inventory.providers.interfaces.request_manager import (
    IGetRequest,
    IPostRequest,
)


class ProviderRequestError(Exception):
    def __init__(self, message: str, is_timeout: bool = False):
        self.message = message
        self.is_timeout = is_timeout
        super().__init__(message)


class RestTransport(IGetRequest, IPostRequest):
    def __init__(self, base_url: str, timeout_seconds: float):
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    def _execute(self, spec: RequestSpec) -> ProviderResponse:
        url = f"{self.base_url.rstrip('/')}/{spec.path.lstrip('/')}"
        try:
            resp = httpx.request(
                spec.method,
                url,
                headers=spec.headers,
                params=spec.params,
                json=spec.json_body,
                timeout=self.timeout_seconds,
            )
            resp.raise_for_status()
            body = resp.json() if resp.content else None
            return ProviderResponse(
                status_code=resp.status_code, json_body=body, raw_text=resp.text
            )
        except httpx.TimeoutException as e:
            raise ProviderRequestError(f"timeout calling {url}", is_timeout=True) from e
        except httpx.HTTPError as e:
            raise ProviderRequestError(f"http error calling {url}: {e}") from e

    def get(
        self, path: str, params: dict | None = None, headers: dict | None = None
    ) -> ProviderResponse:
        return self._execute(RequestSpec(method="GET", path=path, params=params))

    def post(
        self,
        path: str,
        json: dict | None = None,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> ProviderResponse:
        return self._execute(
            RequestSpec(
                method="POST", path=path, json_body=json, headers=headers, params=params
            )
        )
