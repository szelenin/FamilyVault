"""Tool registry + OpenAI schema generation for the custom loop (Phase 1b)."""
import inspect

from tools.photos import search_photos
from tools.projects import (
    list_projects, create_project, get_project, set_timeline,
)

TOOLS = {
    "search_photos": search_photos,
    "list_projects": list_projects,
    "create_project": create_project,
    "get_project": get_project,
    "set_timeline": set_timeline,
}

_PY_TO_JSON = {str: "string", int: "integer", float: "number", bool: "boolean", list: "array"}


def _json_type(annotation):
    return _PY_TO_JSON.get(annotation, "string")


def _schema_for(name, fn):
    sig = inspect.signature(fn)
    props = {}
    required = []
    for pname, param in sig.parameters.items():
        ann = param.annotation if param.annotation is not inspect.Parameter.empty else str
        props[pname] = {"type": _json_type(ann)}
        if param.default is inspect.Parameter.empty:
            required.append(pname)
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": (inspect.getdoc(fn) or "").split("\n\n")[0],
            "parameters": {"type": "object", "properties": props, "required": required},
        },
    }


def openai_schemas():
    """Return OpenAI-format tool schemas for all registered tools."""
    return [_schema_for(name, fn) for name, fn in TOOLS.items()]


def dispatch(name, arguments: dict):
    """Call a registered tool by name with a dict of arguments."""
    if name not in TOOLS:
        raise KeyError(f"unknown tool: {name}")
    return TOOLS[name](**arguments)
