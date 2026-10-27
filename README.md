# Fei 智能助手

Fei 是一个本地单用户、模块化的 LangGraph 智能助手。第一版提供主对话与求职模块；求职不是整个产品，而是首个独立 Subgraph 和业务工作区。

## 已实现范围

- `fei-assistant`：结构化路由 `general / job_search / clarify`，显式模块选择优先。
- `fei-job-search`：独立求职 Subgraph，包含 `job_analysis_agent`、`mail_analysis_agent`、`interview_review_agent`。
- A2A 风格内部边界：`ModuleTask / ModuleMessage / ModuleArtifact`；没有运行正式 A2A Server。
- PostgreSQL：Provider 元数据、岗位、投递事件、邮件建议、面试、复盘和可恢复任务。
- MinIO：简历、面试录音和其它私有文件。
- FastAPI：设置、文件、岗位、投递、邮件、面试和任务接口。
- APScheduler：15 分钟邮件同步、持久化长任务和进程重启恢复。
- assistant-ui + Next.js：主对话、求职工作区、设置；保留 Thread、Message、Composer、流式取消。
- Windows Credential Manager：文本 API Key、DashScope Key、OSS Secret、163 授权码。数据库只保存引用和末四位。

确定性服务拥有写权限。模型只能分析岗位、识别邮件并生成建议、复盘已确认文本；它不能直接改投递状态、操作邮箱或写文件。

## 架构

```text
assistant-ui / Next.js :3000
├─ 主对话 ───────────────> LangGraph API :2024 / fei-assistant
├─ 求职对话 ─────────────> LangGraph API :2024 / fei-job-search
├─ 求职工作区 ───────────> FastAPI :8000
└─ 设置 ─────────────────> FastAPI :8000 -> Windows Credential Manager

FastAPI / APScheduler
├─ PostgreSQL :5432       业务数据、任务、事件历史
├─ MinIO :9000            简历与录音（私有）
├─ 163 IMAP SSL           EXAMINE + UID + BODY.PEEK
└─ Aliyun Paraformer      MinIO -> 临时私有 OSS -> 短时 URL -> 删除临时对象
```

LangGraph API 负责 Thread/Checkpoint 的生命周期；部署时使用其 PostgreSQL 持久化运行时。`langgraph dev` 仅用于开发，进程结束后不应被当作持久化验收环境。业务数据库始终由本项目的 SQLAlchemy/Alembic 管理。

## 环境要求

- Windows 10/11
- Python 3.11+
- Node.js 20+
- Docker Desktop
- 允许当前 Windows 用户访问 Credential Manager

## 首次启动

推荐使用项目脚本。它会补齐某些嵌入式终端缺失的 Windows 环境变量，并使用国内镜像安装依赖：

```powershell
.\scripts\setup.ps1
.\scripts\start.ps1
```

也可以直接双击根目录的 `setup-fei.cmd` 完成首次安装，再双击 `start-fei.cmd` 启动。启动成功后会自动打开 `http://127.0.0.1:3000`。以后再次使用只需执行 `scripts\start.ps1` 或双击 `start-fei.cmd`；停止应用进程执行 `scripts\stop.ps1`，如需同时停止 PostgreSQL/MinIO，则追加 `-Infrastructure`。

下面是等价的手动启动步骤。

### 1. 基础设施

```powershell
Copy-Item .env.example .env
docker-compose up -d
```

默认容器只映射到 `127.0.0.1`。生产密钥不要写入 `.env`；这里只存 PostgreSQL/MinIO 的本地连接参数。

### 2. Python 与数据库

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
alembic upgrade head
```

### 3. FastAPI

```powershell
fei-api
```

API 文档：`http://127.0.0.1:8000/docs`。

### 4. LangGraph API

另开一个 PowerShell：

```powershell
.venv\Scripts\Activate.ps1
langgraph dev --host 127.0.0.1 --port 2024 --no-browser
```

Graph ID：

- `fei-assistant`
- `fei-job-search`

本地开发可用上面的命令；需要验证会话跨重启恢复时，请改用带 PostgreSQL 的 LangGraph API 部署运行时，而不是 in-memory dev runtime。

### 5. Web

```powershell
Set-Location web
Copy-Item .env.example .env.local
npm install
npm run dev
```

打开 `http://127.0.0.1:3000`。第一次使用先进入“设置”：

1. 选择 DeepSeek 预设或自定义 OpenAI-compatible Provider，填写模型和 API Key。
2. 配置 DashScope API Key、Workspace ID、地域域名、私有 OSS Bucket 和 `paraformer-v2`。
3. 配置 163 邮箱与客户端授权码。
4. 分别执行“连接与能力测试”。文本模型会实际测试流式输出、工具调用和 JSON Schema。

## 关键流程

### 岗位分析

上传 PDF/DOCX/TXT 简历，创建岗位并选择简历版本进行分析。报告保存模型、Prompt 版本、输入文档版本和生成时间；输出高/中/低等级以及要求—证据表，不使用百分制匹配分。

### 邮件同步

IMAP 客户端通过 `select(readonly=True)` 发出 `EXAMINE`，用 UID 增量搜索并以 `BODY.PEEK[]` 读取。非求职邮件分析后不落库。相关邮件只产生建议；关联不确定时必须在工作区手工选择投递，确认接口才追加 `application_events`。

### 面试录音

原始录音永久保存在 MinIO。转写任务将其临时写入私有 OSS、生成一小时签名 URL、提交 Paraformer 异步转写，并在 `finally` 中删除 OSS 对象。填写岗位技术词时，服务会创建临时 DashScope 热词表、把 `vocabulary_id` 传给转写任务，并在结束后删除热词表。用户编辑并确认文本后，复盘按钮才可用。

## 数据迁移

```powershell
alembic current
alembic upgrade head
alembic revision --autogenerate -m "describe change"
```

首次迁移位于 `alembic/versions/0001_initial.py`。模型定义集中在 `src/fei_assistant/models.py`。

## 测试

```powershell
python -m pytest -q
Set-Location web
npm run typecheck
npm run build
```

测试覆盖保守路由、显式模块优先、结构化输出失败重试、只读 IMAP、密钥序列化和文件校验。集成环境应使用 PostgreSQL/MinIO 替身、测试邮箱和 Provider stub，不使用真实求职数据。

## 明确不做

- 自动发送或删除邮件、改变邮箱已读状态。
- 招聘网站自动投递。
- 自动改写或虚构简历事实。
- 实时面试陪练。
- 登录、多用户和共享权限。
- 正式 A2A Server / Agent Card。

所有服务默认只绑定 `127.0.0.1`。
