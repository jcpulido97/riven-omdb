import ast
from pathlib import Path


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
