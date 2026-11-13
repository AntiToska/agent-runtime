import pytest
from pydantic import ValidationError

from agent_runtime.tools.add import AddArgs, add


def test_add_returns_sum() -> None:
    args = AddArgs(a=1, b=2)

    assert add(args) == 3


def test_add_args_rejects_string() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AddArgs.model_validate({"a": "1", "b": 2})

    errors = exc_info.value.errors()
    assert len(errors) == 1
    assert errors[0]["loc"] == ("a",)
    assert errors[0]["type"] == "int_type"


def test_add_args_requires_b() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AddArgs.model_validate({"a": 1})

    errors = exc_info.value.errors()
    assert len(errors) == 1
    assert errors[0]["loc"] == ("b",)
    assert errors[0]["type"] == "missing"
