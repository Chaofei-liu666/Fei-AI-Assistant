import asyncio
import os
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage

from .graph import build_graph


async def run_cli() -> None:
    load_dotenv()

    model_id = os.getenv("MODEL_ID")
    if not model_id or "<model-name>" in model_id:
        raise RuntimeError("Set MODEL_ID in .env, for example openai:<model-name>")

    workspace = Path(os.getenv("FEI_WORKSPACE", ".")).resolve()
    model = init_chat_model(model_id, temperature=0)
    graph = build_graph(model=model, workspace=workspace)

    config = {"configurable": {"thread_id": str(uuid4())}}

    print("Fei智能助手已启动。输入 /exit 退出。")
    while True:
        user_input = input("\n你：").strip()
        if user_input.lower() in {"/exit", "/quit"}:
            break
        if not user_input:
            continue

        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=user_input)]},
            config=config,
        )
        print(f"\nFei：{result['messages'][-1].content}")


def main() -> None:
    asyncio.run(run_cli())


if __name__ == "__main__":
    main()

