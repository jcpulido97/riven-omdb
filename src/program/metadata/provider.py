from typing import Protocol

from .models import SeasonMetadata, TitleMetadata


class MetadataProviderError(RuntimeError):
    def __init__(
        self,
        provider: str,
        message: str,
        *,
        http_status: int = 502,
        upstream_status: int | None = None,
    ):
        self.provider = provider
        self.message = message
        self.http_status = http_status
        self.upstream_status = upstream_status
        super().__init__(f"{provider}: {message}")


class MetadataLookupError(RuntimeError):
    def __init__(self, errors: list[MetadataProviderError]):
        self.errors = errors
        self.http_status = errors[0].http_status if errors else 502
        super().__init__("; ".join(str(error) for error in errors))


class MetadataProvider(Protocol):
    name: str

    @property
    def is_configured(self) -> bool: ...

    def get_title(self, imdb_id: str | None) -> TitleMetadata | None: ...

    def get_season(
        self, imdb_id: str | None, season_number: int
    ) -> SeasonMetadata | None: ...
