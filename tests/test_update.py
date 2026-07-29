"""Tests for the opt-in GitHub release check."""

import asyncio
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientError
from homeassistant.const import CONF_SCAN_INTERVAL

from custom_components.audiobookshelf import update as update_module
from custom_components.audiobookshelf.const import (
    CONF_CHECK_FOR_UPDATES,
    check_for_updates_for,
)
from custom_components.audiobookshelf.update import (
    AudiobookshelfUpdate,
    async_setup_entry,
)

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


def _entry(options: dict[str, Any] | None = None) -> Any:
    """Build a config entry stub carrying the given options."""
    coordinator = MagicMock()
    coordinator.api_url = "http://abs.local:13378"
    coordinator.server_version = "2.36.0"
    coordinator.async_refresh_server_version = AsyncMock(return_value="2.36.0")

    entry = MagicMock()
    entry.entry_id = "entry-1"
    entry.options = options if options is not None else {}
    entry.runtime_data = coordinator
    return entry


def _github_returning(payload: Any, *, error: Exception | None = None) -> Any:
    """Build a session whose GitHub call yields payload, or raises."""

    @asynccontextmanager
    async def _get(*_args: Any, **_kwargs: Any) -> Any:
        if error is not None:
            raise error
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json = AsyncMock(return_value=payload)
        yield response

    session = MagicMock()
    session.get = _get
    return session


def _updated(entity: AudiobookshelfUpdate, session: Any) -> None:
    """Run one poll of the entity against the given session."""
    entity.hass = MagicMock()
    with patch.object(update_module, "async_get_clientsession", return_value=session):
        asyncio.run(entity.async_update())


def test_disabled_by_default() -> None:
    """The GitHub check is the one thing that leaves the network."""
    assert check_for_updates_for(_entry()) is False


def test_enabled_when_the_option_is_set() -> None:
    """The options flow toggle is what turns it on."""
    assert check_for_updates_for(_entry({CONF_CHECK_FOR_UPDATES: True})) is True


def test_no_entity_created_when_disabled() -> None:
    """The platform is always forwarded, so opting out must add nothing."""
    added: list[Any] = []
    entry = _entry({CONF_SCAN_INTERVAL: 300})

    add = cast("AddEntitiesCallback", lambda e, _=False: added.extend(e))
    asyncio.run(async_setup_entry(MagicMock(), entry, add))

    assert added == []


def test_entity_created_when_enabled() -> None:
    """Opting in creates exactly one update entity."""
    added: list[Any] = []
    entry = _entry({CONF_CHECK_FOR_UPDATES: True})

    add = cast("AddEntitiesCallback", lambda e, _=False: added.extend(e))
    asyncio.run(async_setup_entry(MagicMock(), entry, add))

    assert len(added) == 1
    assert added[0].unique_id == "entry-1_server_update"


def test_tag_prefix_is_stripped() -> None:
    """Releases are tagged v2.37.0 while the server reports 2.37.0."""
    entry = _entry({CONF_CHECK_FOR_UPDATES: True})
    entity = AudiobookshelfUpdate(entry.runtime_data, entry)

    _updated(entity, _github_returning({"tag_name": "v2.37.0"}))

    assert entity.latest_version == "2.37.0"
    assert entity.installed_version == "2.36.0"
    assert entity.release_url == (
        "https://github.com/advplyr/audiobookshelf/releases/tag/v2.37.0"
    )


def test_matching_versions_report_no_update() -> None:
    """Up to date is the common case and must not offer an update."""
    entry = _entry({CONF_CHECK_FOR_UPDATES: True})
    entity = AudiobookshelfUpdate(entry.runtime_data, entry)

    _updated(entity, _github_returning({"tag_name": "v2.36.0"}))

    assert entity.latest_version == entity.installed_version == "2.36.0"


def test_installed_version_is_re_read_each_poll() -> None:
    """Otherwise the entity offers an update the user has already applied."""
    entry = _entry({CONF_CHECK_FOR_UPDATES: True})
    coordinator = entry.runtime_data
    entity = AudiobookshelfUpdate(coordinator, entry)

    _updated(entity, _github_returning({"tag_name": "v2.37.0"}))

    assert coordinator.async_refresh_server_version.call_count == 1


@pytest.mark.parametrize(
    ("payload", "error"),
    [
        pytest.param(None, ClientError("no route"), id="github-unreachable"),
        pytest.param(None, TimeoutError(), id="github-timeout"),
        pytest.param({"message": "rate limited"}, None, id="no-tag-name"),
        pytest.param(["unexpected"], None, id="not-an-object"),
    ],
)
def test_github_failures_keep_the_last_known_answer(
    payload: Any, error: Exception | None
) -> None:
    """A GitHub blip must not blank the entity, nor touch anything else."""
    entry = _entry({CONF_CHECK_FOR_UPDATES: True})
    entity = AudiobookshelfUpdate(entry.runtime_data, entry)

    _updated(entity, _github_returning({"tag_name": "v2.37.0"}))
    assert entity.latest_version == "2.37.0"

    _updated(entity, _github_returning(payload, error=error))

    assert entity.latest_version == "2.37.0"
    assert entity.installed_version == "2.36.0"


def test_release_url_is_none_before_the_first_answer() -> None:
    """Nothing to link to until GitHub has been reached once."""
    entry = _entry({CONF_CHECK_FOR_UPDATES: True})
    entity = AudiobookshelfUpdate(entry.runtime_data, entry)

    assert entity.latest_version is None
    assert entity.release_url is None
