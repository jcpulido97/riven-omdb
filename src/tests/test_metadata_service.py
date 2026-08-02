from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from program.metadata import (
    EpisodeMetadata,
    MetadataService,
    SeasonMetadata,
    TitleMetadata,
)


@dataclass
class FakeProvider:
    name: str
    result: TitleMetadata | None = None
    season_result: SeasonMetadata | None = None
    is_configured: bool = True
    should_fail: bool = False

    def get_title(self, _imdb_id: str | None) -> TitleMetadata | None:
        if self.should_fail:
            raise RuntimeError("provider unavailable")

        return self.result

    def get_season(
        self, _imdb_id: str | None, _season_number: int
    ) -> SeasonMetadata | None:
        return self.season_result


def test_uses_first_configured_provider_with_metadata():
    expected = TitleMetadata(title="Operation Mincemeat", imdb_id="tt1879016")
    service = MetadataService(
        [
            FakeProvider(name="disabled", is_configured=False),
            FakeProvider(name="empty"),
            FakeProvider(name="working", result=expected),
        ]
    )

    assert service.get_title("tt1879016") == expected


def test_provider_failure_falls_through_to_next_provider():
    expected = TitleMetadata(title="Fallback")
    service = MetadataService(
        [
            FakeProvider(name="failing", should_fail=True),
            FakeProvider(name="fallback", result=expected),
        ]
    )

    assert service.get_title("tt1879016") == expected


def test_lower_priority_provider_fills_missing_fields_only():
    release_date = datetime(2022, 5, 11, tzinfo=UTC)
    service = MetadataService(
        [
            FakeProvider(
                name="primary",
                result=TitleMetadata(
                    title="Preferred Title",
                    imdb_id="tt1879016",
                ),
            ),
            FakeProvider(
                name="secondary",
                result=TitleMetadata(
                    title="Secondary Title",
                    released_at=release_date,
                    media_type="movie",
                ),
            ),
        ]
    )

    result = service.get_title("tt1879016")

    assert result == TitleMetadata(
        title="Preferred Title",
        released_at=release_date,
        imdb_id="tt1879016",
        media_type="movie",
    )


def test_provider_can_be_registered_at_highest_priority():
    service = MetadataService([FakeProvider(name="secondary")])
    primary = FakeProvider(name="primary", result=TitleMetadata(title="Primary"))

    service.register(primary, first=True)

    assert [provider.name for provider in service.providers] == [
        "primary",
        "secondary",
    ]
    assert service.get_title("tt1879016") == primary.result


def test_season_episode_metadata_is_merged_by_episode_number():
    release_date = datetime(2026, 8, 2, tzinfo=UTC)
    service = MetadataService(
        [
            FakeProvider(
                name="primary",
                season_result=SeasonMetadata(
                    number=1,
                    title="Preferred Season",
                    episodes=[EpisodeMetadata(number=1, title="Preferred Episode")],
                ),
            ),
            FakeProvider(
                name="secondary",
                season_result=SeasonMetadata(
                    number=1,
                    title="Secondary Season",
                    episodes=[
                        EpisodeMetadata(number=1, released_at=release_date),
                        EpisodeMetadata(number=2, title="Episode Two"),
                    ],
                ),
            ),
        ]
    )

    result = service.get_season("tt1234567", 1)

    assert result is not None
    assert result.title == "Preferred Season"
    assert result.episodes == [
        EpisodeMetadata(
            number=1,
            title="Preferred Episode",
            released_at=release_date,
        ),
        EpisodeMetadata(number=2, title="Episode Two"),
    ]


def test_duplicate_provider_name_is_rejected():
    service = MetadataService([FakeProvider(name="duplicate")])

    with pytest.raises(ValueError, match="is registered"):
        service.register(FakeProvider(name="duplicate"))
