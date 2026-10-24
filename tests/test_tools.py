from pathlib import Path

import pytest

from fei_assistant.safe_math import calculate_expression
from fei_assistant.tools import build_tools


def test_calculate_expression() -> None:
    assert calculate_expression("(3 + 5) * 2") == 16


def test_calculate_rejects_code() -> None:
    with pytest.raises(ValueError):
        calculate_expression("__import__('os').getcwd()")


def test_workspace_tools_read_local_file(tmp_path: Path) -> None:
    (tmp_path / "note.txt").write_text("hello", encoding="utf-8")
    tools = {item.name: item for item in build_tools(tmp_path)}

    assert tools["list_workspace_files"].invoke({"glob_pattern": "*.txt"}) == ["note.txt"]
    assert tools["read_text_file"].invoke({"relative_path": "note.txt"}) == "hello"


def test_workspace_tool_rejects_parent_path(tmp_path: Path) -> None:
    tools = {item.name: item for item in build_tools(tmp_path)}

    with pytest.raises(ValueError):
        tools["read_text_file"].invoke({"relative_path": "../outside.txt"})

