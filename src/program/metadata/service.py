"""Provider orchestration for release metadata."""

from collections.abc import Iterable

from loguru import logger

from program.metadata.models import EpisodeMetadata, SeasonMetadata, TitleMetadata
from program.metadata.provider import MetadataProvider


class MetadataService:
    """Query configured metadata providers in priority order."""

    def __init__(self, providers: Iterable[MetadataProvider] = ()):
        self._providers = list(providers)

    @property
    def providers(self) -> tuple[MetadataProvider, ...]:
        return tuple(self._providers)

    def register(self, provider: MetadataProvider, *, first: bool = False) -> None:
        """Register a provider, optionally ahead of existing providers."""

        if any(existing.name == provider.name for existing in self._providers):
            raise ValueError(f"Metadata provider {provider.name!r} is registered")

        if first:
            self._providers.insert(0, provider)
        else:
            self._providers.append(provider)

    @property
    def configured_providers(self) -> tuple[MetadataProvider, ...]:
        return tuple(provider for provider in self._providers if provider.is_configured)

    def get_title(self, imdb_id: str | None) -> TitleMetadata | None:
        result = None

        for provider in self.configured_providers:
            try:
                if metadata := provider.get_title(imdb_id):
                    result = self._merge_title(result, metadata)
            except Exception as error:  # noqa: BLE001
                logger.warning(
                    f"Metadata provider {provider.name} failed for {imdb_id}: {error}"
                )

        return result

    def get_season(
        self, imdb_id: str | None, season_number: int
    ) -> SeasonMetadata | None:
        result = None

        for provider in self.configured_providers:
            try:
                if metadata := provider.get_season(imdb_id, season_number):
                    result = self._merge_season(result, metadata)
            except Exception as error:  # noqa: BLE001
                logger.warning(
                    f"Metadata provider {provider.name} failed for "
                    f"{imdb_id} S{season_number}: {error}"
                )

        return result

    @staticmethod
    def _merge_title(
        current: TitleMetadata | None, incoming: TitleMetadata
    ) -> TitleMetadata:
        """Fill missing fields while preserving higher-priority values."""

        if current is None:
            return incoming.model_copy(deep=True)

        return TitleMetadata(
            title=current.title or incoming.title,
            released_at=current.released_at or incoming.released_at,
            imdb_id=current.imdb_id or incoming.imdb_id,
            media_type=current.media_type or incoming.media_type,
        )

    @staticmethod
    def _merge_season(
        current: SeasonMetadata | None, incoming: SeasonMetadata
    ) -> SeasonMetadata:
        """Merge episodes by number while preserving provider priority."""

        if current is None:
            return incoming.model_copy(deep=True)

        episodes = {
            episode.number: episode.model_copy(deep=True)
            for episode in current.episodes
        }

        for incoming_episode in incoming.episodes:
            if current_episode := episodes.get(incoming_episode.number):
                episodes[incoming_episode.number] = EpisodeMetadata(
                    number=current_episode.number,
                    title=current_episode.title or incoming_episode.title,
                    released_at=(
                        current_episode.released_at or incoming_episode.released_at
                    ),
                    imdb_id=current_episode.imdb_id or incoming_episode.imdb_id,
                )
            else:
                episodes[incoming_episode.number] = incoming_episode.model_copy(
                    deep=True
                )

        return SeasonMetadata(
            number=current.number,
            title=current.title or incoming.title,
            episodes=[episodes[number] for number in sorted(episodes)],
        )
