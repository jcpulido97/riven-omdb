import os
from datetime import datetime
from typing import Any

from cachetools import TTLCache
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from requests import RequestException

from program.metadata import normalize_imdb_id
from program.metadata.models import EpisodeMetadata, SeasonMetadata, TitleMetadata
from program.utils.request import create_service_session, get_rate_limit_params


class _OMDbTitleResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str | None = Field(default=None, alias="Title")
    released: str | None = Field(default=None, alias="Released")
    imdb_id: str | None = Field(default=None, alias="imdbID")
    media_type: str | None = Field(default=None, alias="Type")
    year: str | None = Field(default=None, alias="Year")
    genre: str | None = Field(default=None, alias="Genre")
    country: str | None = Field(default=None, alias="Country")
    language: str | None = Field(default=None, alias="Language")
    total_seasons: str | None = Field(default=None, alias="totalSeasons")


class _OMDbEpisodeResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str | None = Field(default=None, alias="Title")
    number: int = Field(alias="Episode")
    released: str | None = Field(default=None, alias="Released")
    imdb_id: str | None = Field(default=None, alias="imdbID")


class _OMDbSeasonResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str | None = Field(default=None, alias="Title")
    season: int = Field(alias="Season")
    episodes: list[_OMDbEpisodeResponse] = Field(default_factory=list, alias="Episodes")


class OMDbAPI:
    name = "omdb"
    BASE_URL = "https://www.omdbapi.com/"

    def __init__(self, api_key: str | None = None):
        configured_key = (
            os.environ.get("OMDB_API_KEY", "") if api_key is None else api_key
        )
        self.api_key = configured_key.strip()
        self._title_cache = TTLCache(maxsize=4096, ttl=86400)
        self._season_cache = TTLCache(maxsize=4096, ttl=21600)
        self.session = create_service_session(
            rate_limit_params=get_rate_limit_params(max_calls=4, period=1)
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _get(self, **params: str | int) -> dict[str, Any] | None:
        if not self.is_configured:
            return None
        try:
            response = self.session.get(
                self.BASE_URL,
                params={"apikey": self.api_key, **params},
                timeout=30,
            )
            if not response.ok:
                logger.debug(f"OMDb request failed with HTTP {response.status_code}")
                return None
            data = response.json()
            if not isinstance(data, dict):
                logger.debug("OMDb returned a non-object JSON response")
                return None
            if data.get("Response") == "False":
                logger.debug(
                    f"OMDb request failed: {data.get('Error', 'unknown error')}"
                )
                return None
            return data
        except (RequestException, ValueError, TypeError) as error:
            logger.debug(f"OMDb request failed: {error}")
            return None

    def get_title(self, imdb_id: str | None) -> TitleMetadata | None:
        imdb_id = normalize_imdb_id(imdb_id)
        if imdb_id is None:
            return None
        if imdb_id in self._title_cache:
            return self._title_cache[imdb_id]
        data = self._get(i=imdb_id, plot="short", r="json")
        try:
            response = _OMDbTitleResponse.model_validate(data) if data else None
            result = self._map_title(response) if response else None
        except ValidationError as error:
            logger.debug(f"Invalid OMDb title response for {imdb_id}: {error}")
            result = None
        if result is not None:
            self._title_cache[imdb_id] = result
        return result

    def get_season(
        self, imdb_id: str | None, season_number: int
    ) -> SeasonMetadata | None:
        imdb_id = normalize_imdb_id(imdb_id)
        if imdb_id is None or season_number < 0:
            return None
        cache_key = (imdb_id, season_number)
        if cache_key in self._season_cache:
            return self._season_cache[cache_key]
        data = self._get(i=imdb_id, Season=season_number, r="json")
        try:
            response = _OMDbSeasonResponse.model_validate(data) if data else None
            result = (
                SeasonMetadata(
                    number=response.season,
                    title=response.title,
                    episodes=[
                        EpisodeMetadata(
                            number=episode.number,
                            title=episode.title,
                            released_at=self.parse_release_date(episode.released),
                            imdb_id=episode.imdb_id,
                        )
                        for episode in response.episodes
                    ],
                )
                if response
                else None
            )
        except ValidationError as error:
            logger.debug(
                f"Invalid OMDb season response for {imdb_id} S{season_number}: {error}"
            )
            result = None
        if result is not None:
            self._season_cache[cache_key] = result
        return result

    @classmethod
    def _map_title(cls, response: _OMDbTitleResponse) -> TitleMetadata:
        year = None
        if response.year and response.year[:4].isdigit():
            year = int(response.year[:4])
        total_seasons = None
        if response.total_seasons and response.total_seasons.isdigit():
            total_seasons = int(response.total_seasons)
        genres = (
            [genre.strip().lower() for genre in response.genre.split(",")]
            if response.genre and response.genre != "N/A"
            else []
        )
        return TitleMetadata(
            title=response.title,
            released_at=cls.parse_release_date(response.released),
            imdb_id=response.imdb_id,
            media_type=response.media_type,
            year=year,
            genres=genres,
            country=None if response.country == "N/A" else response.country,
            language=None if response.language == "N/A" else response.language,
            total_seasons=total_seasons,
        )

    @staticmethod
    def parse_release_date(value: str | None) -> datetime | None:
        if not value or value == "N/A":
            return None
        for date_format in ("%d %b %Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, date_format)
            except ValueError:
                continue
        return None
