"""Tests for the guards on which items remove_my_progress matches."""

import asyncio
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import voluptuous as vol
from aioaudiobookshelf.exceptions import ApiError
from aioaudiobookshelf.schema.library import LibraryItemMinifiedBook
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.audiobookshelf.services import (
    SERVICE_ATTRIBUTE_SERIES_NAME,
    SERVICE_REMOVE_PROGRESS,
    SERVICE_SCHEMAS,
    async_setup_services,
)

SCHEMA = SERVICE_SCHEMAS[SERVICE_REMOVE_PROGRESS]


def _book(item_id: str, series_name: str) -> Any:
    """Build a stand-in book that satisfies the handler's isinstance check."""
    book = MagicMock()
    book.__class__ = LibraryItemMinifiedBook  # type: ignore[assignment]
    book.id_ = item_id
    book.media.metadata.series_name = series_name
    book.media.metadata.title_ignore_prefix = item_id
    return book


def _client(books: list[Any], remove_error: Exception | None = None) -> MagicMock:
    """Build a client serving one library of the given books."""

    async def _get_library_items(library_id: str) -> AsyncIterator[Any]:  # noqa: ARG001
        """Yield one page of results, then an empty page to end pagination."""
        yield SimpleNamespace(results=books)
        yield SimpleNamespace(results=[])

    client = MagicMock()
    client.get_all_libraries = AsyncMock(return_value=[SimpleNamespace(id_="lib-1")])
    client.get_library_items = _get_library_items
    client.get_my_media_progress = AsyncMock(
        side_effect=lambda item_id: SimpleNamespace(id_=f"prog-{item_id}")
    )
    client.remove_my_media_progress = AsyncMock(side_effect=remove_error)
    return client


def _hass(client: MagicMock, state: ConfigEntryState = ConfigEntryState.LOADED) -> Any:
    """Build a hass stub holding a single config entry in the given state."""
    coordinator = MagicMock()
    coordinator.get_client = AsyncMock(return_value=client)
    coordinator.async_request_refresh = AsyncMock()

    entry = MagicMock()
    entry.state = state
    entry.runtime_data = coordinator

    hass = MagicMock()
    hass.config_entries.async_entries.return_value = [entry]
    return hass


def _call(hass: Any, series_name: str) -> None:
    """Register the services and invoke remove_my_progress on the stub."""
    async_setup_services(hass)
    handler = hass.services.async_register.call_args.args[2]
    call = SimpleNamespace(data=SCHEMA({SERVICE_ATTRIBUTE_SERIES_NAME: series_name}))
    asyncio.run(handler(call))


def _removed_progress_for(books: list[Any], series_name: str) -> list[str]:
    """Run the service over one library and return the progress ids it deleted."""
    client = _client(books)
    _call(_hass(client), series_name)
    return [
        c.kwargs["media_progress_id"]
        for c in client.remove_my_media_progress.call_args_list
    ]


@pytest.mark.parametrize("series_name", ["", "   ", "\t\n"])
def test_blank_series_name_is_rejected(series_name: str) -> None:
    """A blank name would substring-match every book, so it must not validate."""
    with pytest.raises(vol.Invalid):
        SCHEMA({SERVICE_ATTRIBUTE_SERIES_NAME: series_name})


def test_missing_series_name_is_rejected() -> None:
    """services.yaml marks the field required; the schema is what enforces it."""
    with pytest.raises(vol.Invalid):
        SCHEMA({})


def test_surrounding_whitespace_is_stripped() -> None:
    """A padded name matches the same items as an unpadded one."""
    assert SCHEMA({SERVICE_ATTRIBUTE_SERIES_NAME: "  Dune  "}) == {
        SERVICE_ATTRIBUTE_SERIES_NAME: "Dune"
    }


def test_only_matching_series_is_removed() -> None:
    """Progress for unrelated series is left alone."""
    books = [
        _book("a", "The Expanse"),
        _book("b", "The Witcher"),
        _book("c", ""),
    ]
    assert _removed_progress_for(books, "Expanse") == ["prog-a"]


def test_match_ignores_case() -> None:
    """A lowercase name still matches a capitalised series."""
    books = [_book("a", "The Expanse")]
    assert _removed_progress_for(books, "expanse") == ["prog-a"]


def test_unconfigured_integration_is_reported() -> None:
    """The action exists even with no entry, so it has to explain itself."""
    hass = _hass(_client([]))
    hass.config_entries.async_entries.return_value = []
    with pytest.raises(ServiceValidationError):
        _call(hass, "Expanse")


def test_unloaded_entry_is_reported() -> None:
    """An entry that failed to load has no coordinator to work with."""
    hass = _hass(_client([]), state=ConfigEntryState.SETUP_ERROR)
    with pytest.raises(ServiceValidationError):
        _call(hass, "Expanse")


def test_api_failure_reports_how_far_it_got() -> None:
    """Deletions cannot be rolled back, so the count so far has to surface."""
    books = [_book("a", "The Expanse"), _book("b", "The Expanse")]
    hass = _hass(_client(books, remove_error=ApiError("server went away")))
    with pytest.raises(HomeAssistantError, match="after 0 item"):
        _call(hass, "Expanse")


def test_refresh_is_requested_even_when_the_run_fails() -> None:
    """A partial run still changed state, so the sensors must be refreshed."""
    hass = _hass(
        _client([_book("a", "The Expanse")], remove_error=ApiError("boom")),
    )
    coordinator = hass.config_entries.async_entries.return_value[0].runtime_data
    with pytest.raises(HomeAssistantError):
        _call(hass, "Expanse")
    assert coordinator.async_request_refresh.await_count == 1
