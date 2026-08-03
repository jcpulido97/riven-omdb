"""Updater module"""
from loguru import logger

from program.media.item import MediaItem
from program.services.updaters.emby import EmbyUpdater
from program.services.updaters.jellyfin import JellyfinUpdater
from program.services.updaters.plex import PlexUpdater


class Updater:
    def __init__(self):
        self.key = "updater"
        self.services = {
            PlexUpdater: PlexUpdater(),
            JellyfinUpdater: JellyfinUpdater(),
            EmbyUpdater: EmbyUpdater(),
        }
        self.initialized = True

    def validate(self) -> bool:
        """Validate that at least one updater service is initialized."""
        initialized_services = [service for service in self.services.values() if service.initialized]
        return len(initialized_services) > 0

    def run(self, item: MediaItem):
        if not self.initialized:
            logger.error("Updater is not initialized properly.")
            return

        initialized_services = [
            service for service in self.services.values() if service.initialized
        ]
        update_succeeded = not initialized_services
        for service_cls, service in self.services.items():
            if service.initialized:
                try:
                    updated_item = next(service.run(item), None)
                    if updated_item is not None:
                        item = updated_item
                        update_succeeded = True
                except Exception as e:
                    logger.error(f"{service_cls.__name__} failed to update {item.log_string}: {e}")

        if not update_succeeded:
            logger.error(
                f"No media server successfully updated {item.log_string}; "
                "leaving it in the Symlinked state"
            )
            return

        for _item in get_items_to_update(item):
            _item.set("update_folder", "updated")
        yield item

def get_items_to_update(item: MediaItem) -> list[MediaItem]:
    """Get items to update for a given item."""
    items_to_update = []
    if item.type in ["movie", "episode"]:
        items_to_update = [item]
    if item.type == "show":
        items_to_update = [e for s in item.seasons for e in s.episodes if e.symlinked and e.get("update_folder") != "updated"]
    elif item.type == "season":
        items_to_update = [e for e in item.episodes if e.symlinked and e.update_folder != "updated"]
    return items_to_update
