# Fei智能助手

Fei智能助手的第一版实现，采用 LangGraph `StateGraph`、`Router` 和 LangChain
`Subagents` 模式。

当前能力：

- 简单请求由主模型直接回答。
- 复杂请求交给 `main agent / supervisor`。
- Supervisor 可以调用 `research_agent`、`coding_agent` 和
  `data_analysis_agent`。
- Subagents 可以读取工作区文本文件，数据分析 Agent 还可以使用安全计算器。
- 使用 `InMemorySaver` 保存当前 CLI 会话的短期状态。

这是有意限制范围的 MVP。当前版本不包含 Web 搜索、文件写入、Shell、数据库、
MCP、长期记忆、Human-in-the-loop 或 Web UI。

## 环境要求

- Python 3.11+
- 一个 LangChain 支持的聊天模型及相应 API Key

## 安装

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

编辑 `.env`：

```dotenv
MODEL_ID=openai:<model-name>
OPENAI_API_KEY=<your-api-key>
FEI_WORKSPACE=.
```

`MODEL_ID` 使用 `langchain.chat_models.init_chat_model` 支持的
`provider:model` 格式。

## 运行

```powershell
fei-assistant
```

或者：

```powershell
python -m fei_assistant.cli
```

输入 `/exit` 退出。

## 测试

```powershell
python -m pytest
```

## 代码结构

```text
src/fei_assistant/
├─ graph.py       # StateGraph、Router、Supervisor
├─ subagents.py   # Subagents-as-tools
├─ tools.py       # 工作区只读工具和计算器
├─ routing.py     # 第一版规则 Router
├─ state.py       # LangGraph State
└─ cli.py         # 命令行入口
```
