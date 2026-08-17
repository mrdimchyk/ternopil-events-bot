import ast
from pathlib import Path


def test_main_uses_render_webhook_runtime():
    source = Path("app/main.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    text = source

    assert "SimpleRequestHandler" in text
    assert "RENDER_EXTERNAL_URL" in text
    assert "web.run_app" in text
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_get"
        for node in ast.walk(tree)
    )
