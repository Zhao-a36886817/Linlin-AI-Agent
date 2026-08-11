from app.main import app


def test_advanced_subsystems_are_not_exposed_by_default() -> None:
    paths = {
        path.lower()
        for route in app.routes
        if isinstance(path := getattr(route, "path", None), str)
    }
    advanced = ("memory", "rag", "mcp", "plugin", "scheduler")

    assert not any(name in path for path in paths for name in advanced)
