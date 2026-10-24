from pathlib import Path

from langchain_core.tools import BaseTool, tool

from .safe_math import calculate_expression


def _resolve_workspace_path(workspace: Path, relative_path: str) -> Path:
    root = workspace.resolve()
    candidate = (root / relative_path).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("Path must stay inside FEI_WORKSPACE")
    return candidate


def build_tools(workspace: Path) -> list[BaseTool]:
    workspace = workspace.resolve()

    @tool
    def list_workspace_files(glob_pattern: str = "**/*") -> list[str]:
        """List up to 100 files in the configured workspace."""

        files: list[str] = []
        for path in workspace.glob(glob_pattern):
            if not path.is_file():
                continue
            relative = path.relative_to(workspace)
            if any(part in {".git", ".venv", "__pycache__"} for part in relative.parts):
                continue
            files.append(relative.as_posix())
            if len(files) == 100:
                break
        return sorted(files)

    @tool
    def read_text_file(relative_path: str) -> str:
        """Read a UTF-8 text file inside the configured workspace."""

        path = _resolve_workspace_path(workspace, relative_path)
        if not path.is_file():
            raise FileNotFoundError(relative_path)
        return path.read_text(encoding="utf-8")[:20_000]

    @tool
    def calculate(expression: str) -> float:
        """Evaluate a numeric arithmetic expression without executing code."""

        return calculate_expression(expression)

    return [list_workspace_files, read_text_file, calculate]

