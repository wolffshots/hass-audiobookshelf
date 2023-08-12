"""pytest fixtures."""
import pytest
from unittest.mock import patch

from requests import HTTPError, Timeout

@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations defined in the test dir."""
    yield

# In this fixture, we are forcing calls to api_wrapper to raise an Exception. This is useful
# for exception handling.
@pytest.fixture(name="error_on_get_data")
def error_get_data_fixture() -> None:
    """Simulate error when retrieving data from API."""
    with patch(
        "custom_components.audiobookshelf.AudiobookshelfApiClient.api_wrapper",
        side_effect=Exception,
    ):
        yield None

@pytest.fixture(name="connectivity_error_on_get_data")
def connectivity_error_get_data_fixture() -> None:
    """Simulate error when retrieving data from API."""
    with patch(
        "custom_components.audiobookshelf.AudiobookshelfApiClient.api_wrapper",
        side_effect=ConnectionError,
    ):
        yield None

@pytest.fixture(name="timeout_error_on_get_data")
def timeout_error_get_data_fixture() -> None:
    """Simulate error when retrieving data from API."""
    with patch(
        "custom_components.audiobookshelf.AudiobookshelfApiClient.api_wrapper",
        side_effect=TimeoutError,
    ):
        yield None

@pytest.fixture(name="http_error_on_get_data")
def http_error_get_data_fixture() -> None:
    """Simulate error when retrieving data from API."""
    with patch(
        "custom_components.audiobookshelf.AudiobookshelfApiClient.api_wrapper",
        side_effect=HTTPError,
    ):
        yield None