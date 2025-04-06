"""Calls to /api/authors."""
from aioaudiobookshelf import AdminClient
from aioaudiobookshelf.schema.user import User


class UsersClient(AdminClient):
    """AuthorsClient."""

    async def get_users(
        self
    ) -> User:
        """ Get all users. """
        response_cls: type[User] = User
        endpoint = f"/api/users"
        response = await self._get(endpoint)
        return response_cls.from_json(response)

    # update author
    # match author
    # get author image