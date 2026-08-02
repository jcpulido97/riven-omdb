"""OMDb API client used for release-date metadata."""

import os
from datetime import datetime
from typing import Any

from cachetools import TTLCache
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from requests import RequestException

from program.utils.request import SmartSession


class OMDbTitle(BaseModel):
    """The subset of an OMDb title response used by Riven."""

    model_config = ConfigDict(populate_by_name=True)

    title: str | None = Field(default=None, alias="Title")
    released: str | None = Field(default=None, alias="Released")
    imdb_id: str | None = Field(default=None, alias="imdbID")
    media_type: str | None = Field(default=None, alias="Type")

    @property
    def released_at(self) -> datetime | None:
        return OMDbAPI.parse_release_date(self.released)


class OMDbEpisode(BaseModel):
    """An episode returned by an OMDb season lookup."""

    model_config = ConfigDict(populate_by_name=True)

    title: str | None = Field(default=None, alias="Title")
    number: int = Field(alias="Episode")
    released: str | None = Field(default=None, alias="Released")
    imdb_id: str | None = Field(default=None, alias="imdbID")

    @property
    def released_at(self) -> datetime | None:
        return OMDbAPI.parse_release_date(self.released)


class OMDbSeason(BaseModel):
    """A season and its episodes returned by OMDb."""

    model_config = ConfigDict(populate_by_name=True)

    title: str | None = Field(default=None, alias="Title")
    season: int = Field(alias="Season")
    episodes: list[OMDbEpisode] = Field(default_factory=list, alias="Episodes")

    @property
    def released_at(self) -> datetime | None:
        dates = [episode.released_at for episode in self.episodes]
        return min(
            (
                date
                for episode, date in zip(self.episodes, dates, strict=True)
                if episode.number > 0 and date is not None
            ),
            default=None,
        )

    def episode_release_dates(self) -> dict[int, datetime]:
        return {
            episode.number: released_at
            for episode in self.episodes
            if (released_at := episode.released_at) is not None
        }


class OMDbAPI:
    """Small OMDb client for title, season, and episode release metadata."""

    BASE_URL = "https://www.omdbapi.com"
    API_KEY = os.environ.get("OMDB_API_KEY", "")

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or self.API_KEY
        self._title_cache = TTLCache[str, OMDbTitle | None](maxsize=4096, ttl=86400)
        self._season_cache = TTLCache[tuple[str, int], OMDbSeason | None](
            maxsize=4096, ttl=21600
        )
        self.session = SmartSession(
            base_url=self.BASE_URL,
            rate_limits={
                "www.omdbapi.com": {
                    "rate": 4,
                    "capacity": 4,
                }
            },
            retries=2,
            backoff_factor=0.3,
        )

    def _get(self, **params: str | int) -> dict[str, Any] | None:
        """Make an OMDb request, always including the configured API key."""

        if not self.api_key:
            logger.debug("OMDB_API_KEY is not configured; skipping OMDb request")
            return None

        try:
            response = self.session.get("/", params={"apikey": self.api_key, **params})

            if not response.ok:
                logger.debug(f"OMDb request failed with HTTP {response.status_code}")
                return None

            data = response.json()

            if data.get("Response") == "False":
                logger.debug(
                    f"OMDb request failed: {data.get('Error', 'unknown error')}"
                )
                return None

            return data
        except (RequestException, ValueError, TypeError) as error:
            logger.debug(f"OMDb request failed: {error}")
            return None

    def get_title(self, imdb_id: str | None) -> OMDbTitle | None:
        if not imdb_id:
            return None

        if imdb_id in self._title_cache:
            return self._title_cache[imdb_id]

        data = self._get(i=imdb_id, plot="short", r="json")

        try:
            result = OMDbTitle.model_validate(data) if data else None
        except ValidationError as error:
            logger.debug(f"Invalid OMDb title response for {imdb_id}: {error}")
            result = None

        self._title_cache[imdb_id] = result
        return result

    def get_season(self, imdb_id: str | None, season_number: int) -> OMDbSeason | None:
        if not imdb_id:
            return None

        cache_key = (imdb_id, season_number)

        if cache_key in self._season_cache:
            return self._season_cache[cache_key]

        data = self._get(i=imdb_id, Season=season_number, r="json")

        try:
            result = OMDbSeason.model_validate(data) if data else None
        except ValidationError as error:
            logger.debug(
                f"Invalid OMDb season response for {imdb_id} S{season_number}: {error}"
            )
            result = None

        self._season_cache[cache_key] = result
        return result

    @staticmethod
    def parse_release_date(value: str | None) -> datetime | None:
        if not value or value == "N/A":
            return None

        for date_format in ("%d %b %Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, date_format)  # noqa: DTZ007
            except ValueError:
                continue

        return None
