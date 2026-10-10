"""Contract test: backend Pydantic models must match frontend/src/types/api.ts exactly.

Checks every model's field names (and optionality) and every Literal enum's values.
Skipped when the frontend directory is not present (e.g. backend-only Docker build).
"""

import re
import typing
from pathlib import Path

import pytest
from pydantic import BaseModel

from app import schemas

TS_FILE = Path(__file__).resolve().parents[2] / "frontend" / "src" / "types" / "api.ts"
pytestmark = pytest.mark.skipif(not TS_FILE.exists(), reason="frontend not checked out")

LITERALS = ["Verdict", "RequirementType", "SectionName", "Priority", "SkillCategory", "SuggestionType"]


def ts_interfaces() -> dict[str, dict[str, bool]]:
    """interface name -> {field: optional}"""
    source = TS_FILE.read_text(encoding="utf-8")
    out = {}
    for name, body in re.findall(r"export interface (\w+) \{(.*?)\n\}", source, re.S):
        fields = {}
        for field, optional in re.findall(r"^\s+(\w+)(\??):", body, re.M):
            fields[field] = optional == "?"
        out[name] = fields
    return out


def ts_union(name: str) -> set[str]:
    source = TS_FILE.read_text(encoding="utf-8")
    match = re.search(rf"export type {name} =(.*?);", source, re.S)
    assert match, f"type {name} missing from api.ts"
    return set(re.findall(r'"([^"]+)"', match.group(1)))


def backend_models() -> dict[str, type[BaseModel]]:
    return {
        name: obj
        for name, obj in vars(schemas).items()
        if isinstance(obj, type)
        and issubclass(obj, BaseModel)
        and obj.__module__ == schemas.__name__
        and not name.startswith("_")
    }


@pytest.mark.parametrize("name", sorted(backend_models()))
def test_model_fields_match_typescript(name):
    interfaces = ts_interfaces()
    assert name in interfaces, f"interface {name} missing from api.ts"
    model = backend_models()[name]
    assert set(model.model_fields) == set(interfaces[name]), f"{name}: field names differ"
    for field, info in model.model_fields.items():
        # A field with a default is optional in the request schema; responses always include it.
        if name.endswith("Request"):
            assert interfaces[name][field] == (not info.is_required()), f"{name}.{field}: optionality differs"


@pytest.mark.parametrize("literal", LITERALS)
def test_literal_values_match_typescript(literal):
    assert set(typing.get_args(getattr(schemas, literal))) == ts_union(literal)
