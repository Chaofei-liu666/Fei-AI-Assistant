# Fei 智能助手

Fei 是一个本地单用户、模块化的 LangGraph 智能助手。它使用 Electron 桌面壳、Next.js 工作空间和 FastAPI 业务层；求职不是整个产品，而是首个完整的 Specialist Subgraph。

## 已实现范围

- `fei-assistant`：结构化路由 `general / job_search / clarify`，显式模块选择优先。
- `fei-job-search`：Supervisor + Specialist Subgraph，包含岗位情报、投递状态、招聘邮件、日程、抓取任务和面试复盘六个 Specialist。
- A2A 风格内部边界：`ModuleTask / ModuleMessage / ModuleArtifact`；没有运行正式 A2A Server。
- PostgreSQL：Provider 元数据、岗位、投递事件、邮件建议、面试、复盘和可恢复任务。
- MinIO：简历、面试录音和其它私有文件。
- FastAPI：稳定的 `/api/career/*` 同源接口，以及设置、文件、面试和任务接口。
- APScheduler：15 分钟邮件同步、持久化长任务和进程重启恢复。
- Electron + Next.js：全新的桌面工作空间、求职数据视图、设置和内置招聘浏览器；assistant-ui 仅承担对话。
- 2027 校招：确定性排除实习、社招和博士限定岗位；匹配使用证据等级，不使用百分制。
- Windows Credential Manager：文本 API Key、DashScope Key、OSS Secret、163 授权码。数据库只保存引用和末四位。

确定性服务拥有写权限。模型只能分析岗位、识别邮件并生成建议、复盘已确认文本；它不能直接改投递状态、操作邮箱或写文件。

## 架构

```text
Fei Electron
├─ Next.js / assistant-ui :3000
├─ 内置招聘浏览器（独立持久化 Session）
└─ 受控 IPC：打开、导航、刷新和官网状态复核

Next.js
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

也可以直接双击根目录的 `setup-fei.cmd` 完成首次安装，再双击 `start-fei.cmd` 启动。健康检查通过后会直接打开 **Fei 桌面应用**，不会再弹出旧的外部浏览器页面。以后再次使用只需执行 `scripts\start.ps1` 或双击 `start-fei.cmd`；停止应用进程执行 `scripts\stop.ps1`，如需同时停止 PostgreSQL/MinIO，则追加 `-Infrastructure`。

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

### 5. Web 与桌面壳

```powershell
Set-Location web
Copy-Item .env.example .env.local
npm install
npm run dev
```

另开一个 PowerShell：

```powershell
Set-Location desktop
npm install
npm start
```

第一次使用先进入“设置”：

1. 选择 DeepSeek 预设或自定义 OpenAI-compatible Provider，填写模型和 API Key。
2. 配置 DashScope API Key、Workspace ID、地域域名、私有 OSS Bucket 和 `paraformer-v2`。
3. 配置 163 邮箱与客户端授权码。
4. 分别执行“连接与能力测试”。文本模型会实际测试流式输出、工具调用、JSON Schema 和可选 Vision。

## 关键流程

### 岗位分析

上传 PDF/DOCX/TXT 简历，先生成并确认候选人画像，再创建或抓取岗位。报告保存模型、Prompt、分析版本、简历版本和输入指纹；输出“推荐关注 / 值得尝试 / 谨慎投入 / 不建议”以及要求—证据表，不使用百分制匹配分。JD、画像、模型或 Prompt 变化后旧分析不会复用。

### 官网状态复核

投递卡片可在 Electron 内置浏览器中打开官网进度页。Fei 不自动填写或提交表单，也不处理验证码；固定的页面观察逻辑只生成 DOM/截图哈希与状态建议。用户确认后才会追加事件，而且官网建议不能降低已有可信阶段。

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
Set-Location ..\desktop
npm run typecheck
npm run build
```

测试覆盖保守路由、2027 校招硬筛选、证据指纹、官网复核确认与状态前进规则、结构化输出失败重试、只读 IMAP、密钥序列化和文件校验。集成环境应使用 PostgreSQL/MinIO 替身、测试邮箱和 Provider stub，不使用真实求职数据。

## 明确不做

- 自动发送或删除邮件、改变邮箱已读状态。
- 招聘网站自动投递。
- 自动改写或虚构简历事实。
- 实时面试陪练。
- 登录、多用户和共享权限。
- 正式 A2A Server / Agent Card。

所有服务默认只绑定 `127.0.0.1`。
