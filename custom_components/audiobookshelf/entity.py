"""AudiobookshelfEntity class"""
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, NAME, VERSION


class AudiobookshelfEntity(CoordinatorEntity):
    """Extends the Coordinator Entity which handles polling"""

    def __init__(
        self,
        coordinator: CoordinatorEntity,
        config_entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self.config_entry = config_entry

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": NAME,
            "model": VERSION,
            "manufacturer": NAME,
        }

    @property
    def device_state_attributes(self) -> dict[str, str]:
        """Return the state attributes."""
        return {
            "attribution": ATTRIBUTION,
            "id": str(self.coordinator.data.get("id")),
            "integration": DOMAIN,
        }
