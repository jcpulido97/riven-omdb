from collections.abc import Iterable

from loguru import logger

from .models import EpisodeMetadata, SeasonMetadata, TitleMetadata
from .provider import MetadataLookupError, MetadataProvider, MetadataProviderError


class MetadataService:
    def __init__(self, providers: Iterable[MetadataProvider] = ()):
        self._providers = list(providers)

    @property
    def providers(self) -> tuple[MetadataProvider, ...]:
        return tuple(self._providers)

    @property
    def configured_providers(self) -> tuple[MetadataProvider, ...]:
        return tuple(provider for provider in self._providers if provider.is_configured)

    def register(self, provider: MetadataProvider, *, first: bool = False) -> None:
        if any(existing.name == provider.name for existing in self._providers):
            raise ValueError(f"Metadata provider {provider.name!r} is registered")
        if first:
            self._providers.insert(0, provider)
        else:
            self._providers.append(provider)

    def get_title(self, imdb_id: str | None) -> TitleMetadata | None:
        result = None
        providers = self._require_configured_providers()
        errors = []
        for provider in providers:
            try:
                if metadata := provider.get_title(imdb_id):
                    result = self._merge_title(result, metadata)
            except MetadataProviderError as error:
                errors.append(error)
                logger.warning(
                    f"Metadata provider {provider.name} failed for {imdb_id}: {error}"
                )
            except Exception as error:
                provider_error = MetadataProviderError(provider.name, str(error))
                errors.append(provider_error)
                logger.exception(
                    f"Metadata provider {provider.name} failed for {imdb_id}: {error}"
                )
        if result is None and errors:
            raise MetadataLookupError(errors)
        return result

    def get_season(
        self, imdb_id: str | None, season_number: int
    ) -> SeasonMetadata | None:
        result = None
        providers = self._require_configured_providers()
        errors = []
        for provider in providers:
            try:
                if metadata := provider.get_season(imdb_id, season_number):
                    result = self._merge_season(result, metadata)
            except MetadataProviderError as error:
                errors.append(error)
                logger.warning(
                    f"Metadata provider {provider.name} failed for "
                    f"{imdb_id} S{season_number}: {error}"
                )
            except Exception as error:
                provider_error = MetadataProviderError(provider.name, str(error))
                errors.append(provider_error)
                logger.exception(
                    f"Metadata provider {provider.name} failed for "
                    f"{imdb_id} S{season_number}: {error}"
                )
        if result is None and errors:
            raise MetadataLookupError(errors)
        return result

    def _require_configured_providers(self) -> tuple[MetadataProvider, ...]:
        providers = self.configured_providers
        if not providers:
            raise MetadataLookupError(
                [
                    MetadataProviderError(
                        "metadata",
                        "No metadata provider is configured",
                        http_status=503,
                    )
                ]
            )
        return providers

    @staticmethod
    def _merge_title(
        current: TitleMetadata | None, incoming: TitleMetadata
    ) -> TitleMetadata:
        if current is None:
            return incoming.model_copy(deep=True)
        return TitleMetadata(
            title=current.title or incoming.title,
            released_at=current.released_at or incoming.released_at,
            imdb_id=current.imdb_id or incoming.imdb_id,
            media_type=current.media_type or incoming.media_type,
            year=current.year or incoming.year,
            genres=current.genres or incoming.genres,
            country=current.country or incoming.country,
            language=current.language or incoming.language,
            total_seasons=current.total_seasons or incoming.total_seasons,
        )

    @staticmethod
    def _merge_season(
        current: SeasonMetadata | None, incoming: SeasonMetadata
    ) -> SeasonMetadata:
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
                    released_at=current_episode.released_at
                    or incoming_episode.released_at,
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
