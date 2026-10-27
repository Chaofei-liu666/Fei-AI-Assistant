from typing import Any

from .contracts import Route


JOB_TASK_MARKERS = (
    "岗位",
    "职位",
    "招聘",
    "jd",
    "简历",
    "经历",
    "项目描述",
    "自我介绍",
    "面试",
    "模拟",
    "复盘",
    "薪资",
    "offer",
    "求职",
    "投递",
    "拒信",
    "招聘邮件",
    "resume",
    "job description",
    "interview",
    "career",
    "salary",
)


def latest_user_text(messages: list[Any]) -> str:
    for message in reversed(messages):
        if message.type == "human":
            return str(message.content)
    return ""


def classify_route(text: str) -> Route:
    """Conservative fallback used only when structured model routing fails."""
    normalized = text.strip().lower()
    if any(marker in normalized for marker in JOB_TASK_MARKERS):
        return "job_search"
    return "general"


def route_for_explicit_module(module: str | None) -> Route | None:
    if module == "job_search":
        return "job_search"
    if module == "general":
        return "general"
    return None

