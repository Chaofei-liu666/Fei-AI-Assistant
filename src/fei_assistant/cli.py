import asyncio
from uuid import uuid4

from dotenv import load_dotenv
from langchain.messages import HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from .config import get_settings
from .db import SessionLocal
from .graph import build_graph
from .providers import build_text_model


async def run_cli() -> None:
    load_dotenv()

    def model_provider():
        with SessionLocal() as db:
            return build_text_model(db)

    checkpoint_url = get_settings().database_url.replace("postgresql+psycopg://", "postgresql://")
    async with AsyncPostgresSaver.from_conn_string(checkpoint_url) as checkpointer:
        await checkpointer.setup()
        graph = build_graph(model_provider, checkpointer=checkpointer)
        config = {"configurable": {"thread_id": str(uuid4())}}

        print("Fei智能助手已启动。输入 /exit 退出。")
        while True:
            user_input = input("\n你：").strip()
            if user_input.lower() in {"/exit", "/quit"}:
                break
            if not user_input:
                continue

            result = await graph.ainvoke(
                {"messages": [HumanMessage(content=user_input)]}, config=config
            )
            print(f"\nFei：{result['messages'][-1].content}")


def main() -> None:
    asyncio.run(run_cli())


if __name__ == "__main__":
    main()

