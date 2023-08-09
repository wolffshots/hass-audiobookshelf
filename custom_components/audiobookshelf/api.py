"""Sample API Client."""
import asyncio
import logging
import socket

import aiohttp
import async_timeout

TIMEOUT = 10


_LOGGER: logging.Logger = logging.getLogger(__package__)

HEADERS = {"Content-type": "application/json; charset=UTF-8"}


class AudiobookshelfApiClient:
    """API Client for communicating with Audiobookshelf server"""

    def __init__(
        self,
        host: str,
        access_token: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Sample API Client."""
        self._host = host
        self._access_token = access_token
        self._session = session

    def get_host(self) -> str:
        """Getter for host var"""
        return self._host

    def count_active_users(self, data: dict) -> int:
        """
        Takes in an object with an array of users
        and counts the active ones minus
        the dummy hass one
        """
        count = 0
        for user in data["users"]:
            if user["isActive"] and user["username"] != "hass":
                if (
                    self._access_token is not None
                    and "token" in user
                    and user["token"] == self._access_token
                ):
                    continue  # Skip user with provided access_token
                count += 1
        return count

    def count_open_sessions(self, data: dict) -> int:
        """
        Counts the number of open stream sessions
        """
        return len(data["openSessions"])

    async def api_wrapper(
        self,
        method: str,
        url: str,
        data: dict | None = None,
        headers: dict | None = None,
    ) -> dict:
        """Get information from the API."""
        if headers is not None:
            headers["Authorization"] = f"Bearer {self._access_token}"
        else:
            headers = {"Authorization": f"Bearer {self._access_token}"}
        try:
            async with async_timeout.timeout(TIMEOUT):  # loop=asyncio.get_event_loop()
                if method == "get":
                    response = await self._session.get(url, headers=headers)
                    return await response.json()

                if method == "put":
                    await self._session.put(url, headers=headers, json=data)

                elif method == "patch":
                    await self._session.patch(url, headers=headers, json=data)

                elif method == "post":
                    await self._session.post(url, headers=headers, json=data)

        except asyncio.TimeoutError as exception:
            _LOGGER.error(
                "Timeout error fetching information from %s - %s",
                url,
                exception,
            )

        except (KeyError, TypeError) as exception:
            _LOGGER.error(
                "Error parsing information from %s - %s",
                url,
                exception,
            )
        except (aiohttp.ClientError, socket.gaierror) as exception:
            _LOGGER.error(
                "Error fetching information from %s - %s",
                url,
                exception,
            )
        except Exception as exception:
            _LOGGER.error("Something really wrong happened! - %s", exception)
            raise exception
