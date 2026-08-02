import ast
from pathlib import Path


def test_manual_session_routes_have_double_prefix_compatibility_aliases():
    module = ast.parse(
        (Path(__file__).parents[1] / "routers" / "secure" / "scrape.py").read_text()
    )
    paths_by_function: dict[str, set[str]] = {}

    for node in module.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        paths_by_function[node.name] = {
            decorator.args[0].value
            for decorator in node.decorator_list
            if isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr == "post"
            and decorator.args
            and isinstance(decorator.args[0], ast.Constant)
            and isinstance(decorator.args[0].value, str)
        }

    assert paths_by_function["start_manual_session"] == {
        "/start_session",
        "/scrape/start_session",
    }
    assert paths_by_function["session_action"] == {
        "/session/{session_id}",
        "/scrape/session/{session_id}",
    }
