import registry


def test_registry_has_five_tools():
    assert set(registry.TOOLS.keys()) == {
        "search_photos", "list_projects", "create_project",
        "get_project", "set_timeline",
    }


def test_openai_schema_shape():
    schemas = registry.openai_schemas()
    by_name = {s["function"]["name"]: s for s in schemas}
    sp = by_name["search_photos"]
    assert sp["type"] == "function"
    params = sp["function"]["parameters"]
    assert params["type"] == "object"
    assert "query" in params["properties"]
    assert params["properties"]["query"]["type"] == "string"
    # create_project: title and request are required (no defaults)
    cp = by_name["create_project"]["function"]["parameters"]
    assert set(cp["required"]) == {"title", "request"}


def test_dispatch_calls_function(monkeypatch):
    called = {}
    monkeypatch.setitem(registry.TOOLS, "create_project",
                        lambda title, request: called.update(title=title, request=request) or {"ok": 1})
    out = registry.dispatch("create_project", {"title": "X", "request": "r"})
    assert out == {"ok": 1}
    assert called == {"title": "X", "request": "r"}
