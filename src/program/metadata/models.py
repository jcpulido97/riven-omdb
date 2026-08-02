"""Provider-neutral metadata models used by Riven indexers."""

from datetime import datetime

from pydantic import BaseModel, Field


class TitleMetadata(BaseModel):
    """Metadata shared by movies and series."""

    title: str | None = None
    released_at: datetime | None = None
    imdb_id: str | None = None
    media_type: str | None = None


class EpisodeMetadata(BaseModel):
    """Provider-neutral episode metadata."""

    number: int
    title: str | None = None
    released_at: datetime | None = None
    imdb_id: str | None = None


class SeasonMetadata(BaseModel):
    """Provider-neutral season metadata."""

    number: int
    title: str | None = None
    episodes: list[EpisodeMetadata] = Field(default_factory=list)

    @property
    def released_at(self) -> datetime | None:
        """Return the earliest regular episode release date."""

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
