from __future__ import annotations

from sqlalchemy import select

ORCHESTRATOR_ID = "orchestrator"

ORCHESTRATOR_DEFAULT = """你是 Fei 的结构化路由器，只输出：
- general：普通问答、写作、分析、公司知识以及其他非求职任务。
- job_search：明确涉及岗位 JD、简历证据匹配、求职投递、招聘邮件、面试记录或 Offer。
- household：记录或查询家里物品的位置与数量，例如「洗衣液放衣柜第二层」「洗衣液在哪」。
- clarify：用户显然要办事但信息不足，无法在以上模块间可靠区分。
普通出现“分析”“公司”“比较”等词不能单独构成 job_search。"""


def get_prompt(agent_id: str, default: str) -> str:
    """Read the user's override, falling back to the built-in prompt.

    Telemetry-style safety: a database hiccup must never stop a run.
    """
    try:
        from .db import SessionLocal
        from .models import AgentPrompt

        with SessionLocal() as db:
            row = db.scalar(select(AgentPrompt).where(AgentPrompt.agent_id == agent_id))
            if row and row.prompt.strip():
                return row.prompt
    except Exception:
        return default
    return default


def read_override(agent_id: str) -> str | None:
    try:
        from .db import SessionLocal
        from .models import AgentPrompt

        with SessionLocal() as db:
            row = db.scalar(select(AgentPrompt).where(AgentPrompt.agent_id == agent_id))
            return row.prompt if row and row.prompt.strip() else None
    except Exception:
        return None


def save_override(agent_id: str, prompt: str) -> None:
    from .db import SessionLocal
    from .models import AgentPrompt

    with SessionLocal() as db:
        row = db.get(AgentPrompt, agent_id) or AgentPrompt(agent_id=agent_id)
        row.prompt = prompt.strip()[:20000]
        db.add(row)
        db.commit()


def reset_override(agent_id: str) -> None:
    from .db import SessionLocal
    from .models import AgentPrompt

    with SessionLocal() as db:
        row = db.get(AgentPrompt, agent_id)
        if row:
            db.delete(row)
            db.commit()
