from typing import Protocol

from .models import SeasonMetadata, TitleMetadata


class MetadataProvider(Protocol):
    name: str

    @property
    def is_configured(self) -> bool: ...

    def get_title(self, imdb_id: str | None) -> TitleMetadata | None: ...

    def get_season(
        self, imdb_id: str | None, season_number: int
    ) -> SeasonMetadata | None: ...
