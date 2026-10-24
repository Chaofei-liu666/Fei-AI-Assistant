from typing import Any

from .contracts import Route


COMPLEX_TASK_MARKERS = (
    "分析",
    "调研",
    "比较",
    "规划",
    "执行",
    "代码",
    "编程",
    "bug",
    "测试",
    "文件",
    "数据",
    "csv",
    "excel",
    "报告",
    "多个",
    "步骤",
    "research",
    "analyze",
    "compare",
    "code",
    "debug",
    "data",
    "report",
)


def latest_user_text(messages: list[Any]) -> str:
    for message in reversed(messages):
        if message.type == "human":
            return str(message.content)
    return ""


def classify_route(text: str) -> Route:
    normalized = text.strip().lower()
    if len(normalized) >= 80:
        return "supervisor"
    if any(marker in normalized for marker in COMPLEX_TASK_MARKERS):
        return "supervisor"
    return "direct"

