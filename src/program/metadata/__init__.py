"""Pluggable metadata provider interfaces and orchestration."""

from program.metadata.models import EpisodeMetadata, SeasonMetadata, TitleMetadata
from program.metadata.provider import MetadataProvider
from program.metadata.service import MetadataService

__all__ = [
    "EpisodeMetadata",
    "MetadataProvider",
    "MetadataService",
    "SeasonMetadata",
    "TitleMetadata",
]
