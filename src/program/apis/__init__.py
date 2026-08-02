from kink import di
from loguru import logger

from program.metadata import MetadataService
from program.settings import settings_manager

from .listrr_api import ListrrAPI
from .mdblist_api import MdblistAPI
from .omdb_api import OMDbAPI
from .overseerr_api import OverseerrAPI
from .plex_api import PlexAPI
from .tmdb_api import TMDBApi
from .trakt_api import TraktAPI
from .tvdb_api import TVDBApi


def bootstrap_apis():
    __setup_plex()
    __setup_mdblist()
    __setup_overseerr()
    __setup_listrr()
    __setup_trakt()
    __setup_metadata()
    __setup_tmdb()
    __setup_tvdb()


def __setup_trakt():
    di[TraktAPI] = TraktAPI(settings_manager.settings.content.trakt)


def __setup_metadata():
    omdb = OMDbAPI()
    metadata = MetadataService()
    metadata.register(omdb)
    di[OMDbAPI] = omdb
    di[MetadataService] = metadata

    if omdb.is_configured:
        logger.success("OMDb release metadata provider initialized")
    else:
        logger.warning(
            "OMDB_API_KEY is not configured; release metadata will fall back "
            "to TMDB and TVDB"
        )


def __setup_tmdb():
    di[TMDBApi] = TMDBApi()


def __setup_tvdb():
    di[TVDBApi] = TVDBApi()


def __setup_plex():
    if not settings_manager.settings.updaters.plex.enabled:
        return

    di[PlexAPI] = PlexAPI(
        settings_manager.settings.updaters.plex.token,
        settings_manager.settings.updaters.plex.url,
    )


def __setup_overseerr():
    if not settings_manager.settings.content.overseerr.enabled:
        return

    di[OverseerrAPI] = OverseerrAPI(
        settings_manager.settings.content.overseerr.api_key,
        settings_manager.settings.content.overseerr.url,
    )


def __setup_mdblist():
    if not settings_manager.settings.content.mdblist.enabled:
        return

    di[MdblistAPI] = MdblistAPI(settings_manager.settings.content.mdblist.api_key)


def __setup_listrr():
    if not settings_manager.settings.content.listrr.enabled:
        return

    di[ListrrAPI] = ListrrAPI(settings_manager.settings.content.listrr.api_key)
