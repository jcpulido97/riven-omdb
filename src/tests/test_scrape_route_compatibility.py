import ast
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from program.metadata import MetadataLookupError, MetadataProviderError
from program.services.downloaders import Downloader
from program.services.indexers.omdb import OMDbIndexer
from routers.secure.scrape import router, session_manager


def _post_paths() -> dict[str, set[str]]:
    module = ast.parse(
        (Path(__file__).parents[1] / "routers" / "secure" / "scrape.py").read_text()
    )
    paths = {}
    for node in module.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        paths[node.name] = {
            decorator.args[0].value
            for decorator in node.decorator_list
            if isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr == "post"
            and decorator.args
            and isinstance(decorator.args[0], ast.Constant)
            and isinstance(decorator.args[0].value, str)
        }
    return paths


def test_manual_session_routes_support_both_prefix_styles():
    paths = _post_paths()
    assert paths["start_manual_session"] == {
        "/start_session",
        "/scrape/start_session",
    }
    assert paths["manual_select_files"] == {
        "/select_files/{session_id}",
        "/scrape/select_files/{session_id}",
    }
    assert paths["session_action"] == {
        "/session/{session_id}",
        "/scrape/session/{session_id}",
    }


def test_start_session_bubbles_up_omdb_quota_error():
    class FailingIndexer:
        def run(self, _item):
            raise MetadataLookupError(
                [
                    MetadataProviderError(
                        "omdb",
                        "Request limit reached!",
                        http_status=429,
                        upstream_status=401,
                    )
                ]
            )
            yield

    app = FastAPI()
    app.program = SimpleNamespace(
        services={OMDbIndexer: FailingIndexer(), Downloader: object()}
    )
    app.include_router(router, prefix="/api/v1")
    session_manager.downloader = None

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/scrape/scrape/start_session",
            params={
                "item_id": "tt1879016",
                "magnet": (
                    "https://addon.peerflix.mov/realdebrid/provider-token/"
                    "a597664fa90231296b701882f018240c8606529f/null/0/movie.mkv"
                ),
            },
        )

    assert response.status_code == 429
    assert response.json() == {"detail": "omdb: Request limit reached!"}
