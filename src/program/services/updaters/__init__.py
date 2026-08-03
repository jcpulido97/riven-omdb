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

        for service_cls, service in self.services.items():
            if service.initialized:
                try:
                    updated_item = next(service.run(item), None)
                    if updated_item is not None:
                        item = updated_item
                except Exception as e:
                    logger.error(f"{service_cls.__name__} failed to update {item.log_string}: {e}")

        # Media-server refreshes are optional notifications, not confirmation
        # that the symlink workflow completed. Once every configured updater has
        # been attempted, mark the item updated even if a service returned no
        # item or raised; otherwise it remains Symlinked forever and is retried
        # on every state transition.
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
