from datetime import datetime

from pydantic import BaseModel, Field


class TitleMetadata(BaseModel):
    title: str | None = None
    released_at: datetime | None = None
    imdb_id: str | None = None
    media_type: str | None = None
    year: int | None = None
    genres: list[str] = Field(default_factory=list)
    country: str | None = None
    language: str | None = None
    total_seasons: int | None = None


class EpisodeMetadata(BaseModel):
    number: int
    title: str | None = None
    released_at: datetime | None = None
    imdb_id: str | None = None


class SeasonMetadata(BaseModel):
    number: int
    title: str | None = None
    episodes: list[EpisodeMetadata] = Field(default_factory=list)

    @property
    def released_at(self) -> datetime | None:
        return min(
            (
                episode.released_at
                for episode in self.episodes
                if episode.number > 0 and episode.released_at is not None
            ),
            default=None,
        )

    def episode_release_dates(self) -> dict[int, datetime]:
        return {
            episode.number: episode.released_at
            for episode in self.episodes
            if episode.released_at is not None
        }
