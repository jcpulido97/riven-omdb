from datetime import datetime, timedelta
from typing import Generator, Union

from kink import di
from loguru import logger

from program.apis.cinemeta_api import CinemetaAPI
from program.media.item import Episode, MediaItem, Movie, Season, Show
from program.metadata import MetadataService, SeasonMetadata, TitleMetadata
from program.settings.manager import settings_manager


class OMDbIndexer:
    """Build Riven media items from pluggable IMDb metadata providers."""

    key = "omdbindexer"

    def __init__(self):
        self.ids = []
        self.initialized = True
        self.settings = settings_manager.settings.indexer
        self.metadata = di[MetadataService]
        self.identifiers = di[CinemetaAPI]

    @staticmethod
    def copy_attributes(source, target):
        attributes = [
            "id",
            "trakt_id",
            "tvdb_id",
            "tmdb_id",
            "file",
            "folder",
            "alternative_folder",
            "update_folder",
            "symlinked",
            "is_anime",
            "symlink_path",
            "subtitles",
            "requested_by",
            "requested_at",
            "overseerr_id",
            "active_stream",
            "requested_id",
            "streams",
        ]
        for attr in attributes:
            value = getattr(source, attr, None)
            if attr in ("trakt_id", "tvdb_id", "tmdb_id") and value is None:
                continue
            target.set(attr, value)

    def copy_items(self, source: MediaItem, target: MediaItem):
        is_anime = source.is_anime or target.is_anime
        if target.type == "show" and source.type != "movie":
            return self._copy_show(source, target, is_anime)
        if target.type == "movie":
            self.copy_attributes(source, target)
            if source.type == "mediaitem":
                target.id = f"movie_{target.imdb_id}"
            target.set("is_anime", is_anime)
            return target
        logger.error(
            f"Item types {source.type} and {target.type} do not match; "
            "cannot copy metadata"
        )
        return target

    def _copy_show(self, source: MediaItem, target: MediaItem, is_anime: bool):
        if source.type == "mediaitem":
            source.seasons = target.seasons
        elif source.id:
            target.id = source.id
        for source_season in source.seasons:
            target_season = next(
                (
                    season
                    for season in target.seasons
                    if season.number == source_season.number
                ),
                None,
            )
            if target_season is None:
                continue
            target_season.id = source_season.id
            for source_episode in source_season.episodes:
                target_episode = next(
                    (
                        episode
                        for episode in target_season.episodes
                        if episode.number == source_episode.number
                    ),
                    None,
                )
                if target_episode:
                    self.copy_attributes(source_episode, target_episode)
                    target_episode.set("is_anime", is_anime)
            target_season.set("is_anime", is_anime)
        target.set("is_anime", is_anime)
        return target

    def run(
        self, in_item: MediaItem, log_msg: bool = True
    ) -> Generator[Union[Movie, Show, Season, Episode], None, None]:
        if not in_item or not in_item.imdb_id:
            logger.error("Item does not have an IMDb ID, cannot index it")
            return
        metadata = self.metadata.get_title(in_item.imdb_id)
        item = self._create_title(metadata) if metadata else None
        if item is None:
            logger.error(f"Failed to index item with IMDb ID: {in_item.imdb_id}")
            return

        expected_type = in_item.type if in_item.type != "mediaitem" else None
        if expected_type and item.type != expected_type:
            logger.error(
                f"Indexed IMDb ID {in_item.imdb_id} as {item.type}, "
                f"expected {expected_type}"
            )
            return

        if isinstance(item, Show):
            self._add_seasons_to_show(item, metadata)

        external_ids = self.identifiers.get_external_ids(
            metadata.imdb_id, metadata.media_type
        )
        item.tmdb_id = external_ids.tmdb_id
        item.tvdb_id = external_ids.tvdb_id

        item = self.copy_items(in_item, item)
        item.indexed_at = datetime.now()
        if log_msg:
            logger.info(
                f"Indexed IMDb ID ({in_item.imdb_id}) as "
                f"{item.type.title()}: {item.log_string}"
            )
        yield item

    @staticmethod
    def should_submit(item: MediaItem) -> bool:
        if not item.indexed_at or not item.title:
            return True
        settings = settings_manager.settings.indexer
        interval = timedelta(seconds=settings.update_interval)
        return datetime.now() - item.indexed_at > interval

    def _create_title(self, metadata: TitleMetadata) -> Movie | Show | None:
        media_type = "show" if metadata.media_type == "series" else metadata.media_type
        if media_type not in ("movie", "show") or not metadata.imdb_id:
            return None
        country = self._country_code(metadata.country)
        item = {
            "id": f"{media_type}_{metadata.imdb_id}",
            "title": metadata.title,
            "year": metadata.year,
            "aired_at": metadata.released_at,
            "imdb_id": metadata.imdb_id,
            "genres": metadata.genres,
            "country": country,
            "language": metadata.language,
            "requested_at": datetime.now(),
            "type": media_type,
            "aliases": {"us": [metadata.title]} if metadata.title else {},
        }
        item["is_anime"] = self._is_anime(item)
        return Movie(item) if media_type == "movie" else Show(item)

    def _add_seasons_to_show(self, show: Show, title: TitleMetadata) -> None:
        for season_number in range(1, (title.total_seasons or 0) + 1):
            season = self.metadata.get_season(show.imdb_id, season_number)
            if season:
                show.add_season(self._create_season(show, season))

    @staticmethod
    def _create_season(show: Show, metadata: SeasonMetadata) -> Season:
        season = Season(
            {
                "id": f"season_{show.imdb_id}_{metadata.number}",
                "title": metadata.title,
                "number": metadata.number,
                "aired_at": metadata.released_at,
                "year": metadata.released_at.year if metadata.released_at else None,
                "type": "season",
            }
        )
        for episode_metadata in metadata.episodes:
            episode_id = episode_metadata.imdb_id or (
                f"{show.imdb_id}_{metadata.number}_{episode_metadata.number}"
            )
            episode = Episode(
                {
                    "id": f"episode_{episode_id}",
                    "title": episode_metadata.title,
                    "number": episode_metadata.number,
                    "aired_at": episode_metadata.released_at,
                    "year": (
                        episode_metadata.released_at.year
                        if episode_metadata.released_at
                        else None
                    ),
                    "imdb_id": episode_metadata.imdb_id,
                    "type": "episode",
                }
            )
            season.add_episode(episode)
        return season

    @staticmethod
    def _country_code(country: str | None) -> str | None:
        if not country:
            return None
        primary = country.split(",", maxsplit=1)[0].strip().lower()
        return {
            "united states": "us",
            "usa": "us",
            "japan": "jp",
            "south korea": "kr",
            "china": "cn",
            "hong kong": "hk",
        }.get(primary, primary)

    @staticmethod
    def _is_anime(item: dict) -> bool:
        return bool(
            item.get("country") in {"jp", "kr", "cn", "hk"}
            and any(
                genre in item.get("genres", [])
                for genre in ("animation", "donghua", "anime")
            )
        )
