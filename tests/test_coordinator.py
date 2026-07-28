"""Tests for the response schemas used by the coordinator."""

import time
from types import SimpleNamespace

from custom_components.audiobookshelf.audiobook_shelf_data_update_coordinator import (
    AuthSessionsResponse,
    LibraryStats,
    OpenSessionsResponse,
)


def test_auth_sessions_uses_total_not_page_length() -> None:
    """Total reflects the full count, not the paginated sessions list."""
    payload = b"""
    {"total": 7, "numPages": 1, "page": 0, "itemsPerPage": 10,
     "sessions": [{"id": "a"}, {"id": "b"}]}
    """
    assert AuthSessionsResponse.from_json(payload).total == 7


def test_library_stats_without_total_authors() -> None:
    """Podcast libraries omit totalAuthors, which must not fail parsing."""
    payload = b"""
    {"totalGenres": 3, "totalItems": 12, "totalSize": 1024,
     "totalDuration": 60.5, "numAudioTracks": 40}
    """
    stats = LibraryStats.from_json(payload)
    assert stats.total_authors is None
    assert stats.total_items == 12
    assert stats.total_size == 1024


def test_library_stats_with_total_authors() -> None:
    """Book libraries include totalAuthors."""
    payload = b"""
    {"totalAuthors": 5, "totalGenres": 3, "totalItems": 12, "totalSize": 1024,
     "totalDuration": 60.5, "numAudioTracks": 40}
    """
    assert LibraryStats.from_json(payload).total_authors == 5


def _response_with_session_at(updated_at_ms: int) -> OpenSessionsResponse:
    """Build a response around a stand-in that only carries updated_at."""
    return OpenSessionsResponse(sessions=[SimpleNamespace(updated_at=updated_at_ms)])  # type: ignore[list-item]


def test_recent_session_is_kept() -> None:
    """A session updated just now counts as active."""
    response = _response_with_session_at(int(time.time() * 1000))
    assert len(response.filter_active_sessions()) == 1


def test_stale_session_is_filtered_out() -> None:
    """A session idle beyond the threshold is not active."""
    stale_ms = int(time.time() * 1000) - (10 * 60 * 1000)
    response = _response_with_session_at(stale_ms)
    assert response.filter_active_sessions() == []
    assert len(response.sessions) == 1


def test_idle_threshold_boundary_is_respected() -> None:
    """A custom idle window changes which sessions are considered active."""
    ninety_seconds_ago = int(time.time() * 1000) - (90 * 1000)
    response = _response_with_session_at(ninety_seconds_ago)
    assert len(response.filter_active_sessions(max_idle_seconds=120)) == 1
    assert response.filter_active_sessions(max_idle_seconds=60) == []
