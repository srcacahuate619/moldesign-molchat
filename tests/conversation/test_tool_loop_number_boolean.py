"""The closed tool schemas now understand numbers and booleans, and stay as strict as the rest."""
import json

import pytest

from molchat_agent.conversation.tool_loop import _arguments

SCHEMA = {"type": "object", "properties": {
    "threshold": {"type": "number", "minimum": -30, "maximum": 0}, "flag": {"type": "boolean"}},
    "required": ["threshold"], "additionalProperties": False}


def parse(**values):
    return _arguments(json.dumps(values), SCHEMA)


def test_numbers_and_booleans_pass_within_their_range():
    assert parse(threshold=-9.5, flag=True) == {"threshold": -9.5, "flag": True}
    assert parse(threshold=-9) == {"threshold": -9}
    assert parse(threshold="-9.5") == {"threshold": -9.5}  # a model that writes the number as text still works


@pytest.mark.parametrize("value", [5, 0.1, -31, True, "abc", "NaN", None, [1], "-9,5", "1e3"])
def test_numbers_outside_the_range_or_of_another_kind_are_refused(value):
    with pytest.raises(ValueError):
        parse(threshold=value)


@pytest.mark.parametrize("value", ["true", 1, 0, None, "si"])
def test_a_boolean_is_only_a_boolean(value):
    with pytest.raises(ValueError):
        parse(threshold=-9, flag=value)


def test_a_number_schema_without_bounds_is_not_accepted():
    schema = {"type": "object", "properties": {"x": {"type": "number"}}, "required": ["x"], "additionalProperties": False}
    with pytest.raises(ValueError):
        _arguments(json.dumps({"x": 1}), schema)
