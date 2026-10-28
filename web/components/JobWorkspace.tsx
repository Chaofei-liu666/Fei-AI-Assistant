"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { api, upload } from "@/lib/api";
import { Icon } from "./Icon";

type Dashboard = { counts: Record<string, number>; today: string; task?: Task };
type Profile = { id: string; document_id: string; document_version: number; degree?: string; job_type?: string; target_directions: string[]; title_keywords: string[]; excluded_title_keywords: string[]; skills: string[]; project_evidence: string[]; supporting_skills: string[]; learning_targets: string[]; confirmed: boolean };
type Evidence = { requirement: string; evidence?: string; assessment: "direct" | "adjacent" | "missing"; requirement_type: "core" | "supporting" | "basic"; source_quote?: string };
type Analysis = { id: string; evidence_level: string; label: string; model: string; prompt_version: string; analysis_version: string; document_version: number; created_at: string; result: { summary: string; evidence_table: Evidence[]; missing_core_requirements: string[]; advantages: string[]; gaps: string[]; risks: string[]; preparation_actions: string[] } };
type Job = { id: string; company: string; title: string; description: string; source_url?: string; city?: string; cohort: number; batch: string; source_kind: string; jd_status: string; first_seen_at: string; latest_analysis?: Analysis };
type Source = { id: string; company: string; entry_url: string; source_kind: string; status: string; last_error?: string; last_attempted_at?: string; job_count: number; incomplete_jd_count: number };
type Application = { id: string; job_id: string; company_name: string; job_title: string; status: string; record_url?: string; updated_at: string };
type ApplicationEvent = { id: string; from_status?: string; to_status: string; source: string; note?: string; evidence?: Record<string, unknown>; created_at: string };
type Suggestion = { id: string; subject: string; sender: string; body_summary: string; mail_type: string; application_id?: string; suggested_status?: string; confidence: number; rationale: string };
type ScheduleItem = { id: string; application_id?: string; title: string; item_type: string; event_date?: string; deadline_at?: string; status: string; source: string; note?: string };
type Automation = { id: string; name: string; task_kind: string; schedule_time: string; timezone: string; enabled: boolean; last_run_at?: string; last_status?: string; last_error?: string };
type Review = { overview: string; answers: { question: string; answer: string; strengths: string[]; missing_evidence: string[]; structure_issues: string[]; improvements: string[] }[]; practice_questions: string[] };
type Interview = { id: string; job_id?: string; application_id?: string; company: string; job_title?: string; scheduled_at?: string; round?: string; outcome?: string; transcript?: string; transcript_confirmed: boolean; audio_document_id?: string; latest_review?: { result: Review; model: string } };
type Doc = { id: string; filename: string; version: number };
type Task = { id: string; kind: string; status: string; progress: number; error?: string; updated_at: string; result?: Record<string, unknown> };

const statusLabels: Record<string, string> = { saved: "收藏", applied: "已投递", screening: "筛选中", assessment: "测评", interview: "面试", offer: "Offer", rejected: "拒绝", withdrawn: "撤回" };
const statuses = Object.keys(statusLabels);
const evidenceLabels: Record<string, string> = { direct: "推荐关注", partial: "值得尝试", adjacent: "谨慎投入", insufficient: "不建议" };

export function JobWorkspace({ tab, onTab }: { tab: string; onTab: (tab: string) => void }) {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [schedule, setSchedule] = useState<ScheduleItem[]>([]);
  const [automations, setAutomations] = useState<Automation[]>([]);
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [docs, setDocs] = useState<Doc[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [notice, setNotice] = useState("");
  const refresh = useCallback(async () => {
    const [d, p, j, c, a, m, s, au, i, files, t] = await Promise.all([
      api<Dashboard>("/api/career/dashboard"), api<Profile | null>("/api/career/profile"),
      api<{items: Job[]}>("/api/career/jobs"), api<Source[]>("/api/career/companies"),
      api<Application[]>("/api/career/applications"), api<Suggestion[]>("/api/career/mail"),
      api<ScheduleItem[]>("/api/career/schedule"), api<Automation[]>("/api/career/automations"),
      api<Interview[]>("/api/interviews"), api<Doc[]>("/api/files?kind=resume"), api<Task[]>("/api/career/tasks?limit=20"),
    ]);
    setDashboard(d); setProfile(p); setJobs(j.items); setSources(c); setApplications(a); setSuggestions(m);
    setSchedule(s); setAutomations(au); setInterviews(i); setDocs(files); setTasks(t);
  }, []);
  useEffect(() => { void refresh().catch((error) => setNotice(error.message)); const timer = setInterval(() => void refresh().catch(() => undefined), 8000); return () => clearInterval(timer); }, [refresh]);
  const run = async (work: () => Promise<unknown>, message: string) => { try { await work(); setNotice(message); await refresh(); } catch (error) { setNotice(error instanceof Error ? error.message : "操作失败"); } };

  return <div className="workspace-scroll career-workspace">
    {notice && <button className="notice" onClick={() => setNotice("")}>{notice}<Icon name="close" size={14} /></button>}
    {tab === "overview" && <Overview dashboard={dashboard} tasks={tasks} onTab={onTab} />}
    {tab === "profile" && <ProfilePanel profile={profile} docs={docs} run={run} />}
    {tab === "jobs" && <Jobs jobs={jobs} docs={docs} profile={profile} applications={applications} run={run} />}
    {tab === "companies" && <Companies sources={sources} run={run} />}
    {tab === "applications" && <Applications applications={applications} run={run} />}
    {tab === "mail" && <Mail suggestions={suggestions} applications={applications} run={run} />}
    {tab === "schedule" && <Schedule items={schedule} applications={applications} run={run} />}
    {tab === "interviews" && <Interviews interviews={interviews} applications={applications} run={run} />}
    {tab === "automations" && <Automations items={automations} tasks={tasks} run={run} />}
  </div>;
}

function PageHeading({ eyebrow, title, copy, actions }: { eyebrow: string; title: string; copy: string; actions?: React.ReactNode }) {
  return <div className="workspace-heading"><div><p className="eyebrow">{eyebrow}</p><h2>{title}</h2><p>{copy}</p></div>{actions && <div className="heading-actions">{actions}</div>}</div>;
}

function Overview({ dashboard, tasks, onTab }: { dashboard: Dashboard | null; tasks: Task[]; onTab: (tab: string) => void }) {
  const cards = [
    ["2027 校招岗位", dashboard?.counts.jobs ?? 0, "jobs", "target"], ["进行中投递", dashboard?.counts.applications ?? 0, "applications", "columns"],
    ["待确认邮件", dashboard?.counts.mail_pending ?? 0, "mail", "mail"], ["日程与待办", dashboard?.counts.schedule_pending ?? 0, "schedule", "clock"],
  ] as const;
  return <><PageHeading eyebrow="CAREER OPERATIONS" title="求职总览" copy="围绕 2027 届校招，把岗位证据、投递、邮件、日程与面试放在同一条可追溯链路中。" />
    <div className="metric-grid">{cards.map(([label, value, target, icon]) => <button className="metric-card" key={label} onClick={() => onTab(target)}><span className="metric-icon"><Icon name={icon} /></span><strong>{value}</strong><span>{label}</span></button>)}</div>
    <section className="workspace-card focus-card"><div><p className="eyebrow">NEXT ACTION</p><h3>{dashboard?.counts.jobs ? "查看证据充分的岗位" : "先上传简历并建立候选人画像"}</h3><p>{dashboard?.counts.jobs ? "岗位按证据等级、直接核心证据和核心缺口排序，不使用百分制匹配分。" : "画像只提取简历明确事实，确认后才会用于岗位匹配。"}</p></div><button className="primary" onClick={() => onTab(dashboard?.counts.jobs ? "jobs" : "profile")}>继续 <Icon name="arrow" size={14} /></button></section>
    <section className="workspace-card"><div className="section-title"><div><p className="eyebrow">DURABLE TASKS</p><h3>最近任务</h3></div><button className="ghost" onClick={() => onTab("automations")}>全部任务</button></div><TaskList tasks={tasks.slice(0, 6)} /></section>
    <div className="boundary-grid"><article><Icon name="check" /><b>Agent 可以做</b><p>查询岗位、证据、投递、邮件摘要、日程和任务状态。</p></article><article><Icon name="alert" /><b>必须由你确认</b><p>投递阶段、邮件关联、官网复核结果和转写文本。</p></article><article><Icon name="lock" /><b>始终禁止</b><p>自动投递、自动填表、绕过验证码、发送或删除邮件。</p></article></div>
  </>;
}

function ProfilePanel({ profile, docs, run }: { profile: Profile | null; docs: Doc[]; run: Runner }) {
  const [selected, setSelected] = useState("");
  const [draft, setDraft] = useState<Profile | null>(profile);
  useEffect(() => setDraft(profile), [profile]);
  const list = (key: keyof Profile, label: string) => <label className="field-stack"><span>{label}</span><textarea value={Array.isArray(draft?.[key]) ? (draft?.[key] as string[]).join("\n") : ""} onChange={(e) => draft && setDraft({...draft, [key]: e.target.value.split("\n").map(x => x.trim()).filter(Boolean)})} /></label>;
  return <><PageHeading eyebrow="CANDIDATE PROFILE" title="候选人画像" copy="原始简历保存在 MinIO；画像只保留经过你确认的学历、技能、方向和项目事实。" actions={<label className="file-button"><Icon name="upload" size={15} /> 上传简历<input type="file" accept=".pdf,.docx,.txt" onChange={(e) => e.target.files?.[0] && run(() => upload("/api/files?kind=resume", e.target.files![0]), "简历已上传")} /></label>} />
    <section className="workspace-card profile-source"><select value={selected} onChange={(e) => setSelected(e.target.value)}><option value="">选择简历版本</option>{docs.map(doc => <option key={doc.id} value={doc.id}>{doc.filename} · v{doc.version}</option>)}</select><button className="primary" disabled={!selected} onClick={() => run(() => api(`/api/career/profile/from-document/${selected}`, {method:"POST"}), "候选人画像已生成，请核对并确认")}>生成画像</button></section>
    {!draft ? <Empty title="还没有候选人画像" copy="上传文字版 PDF、DOCX 或 TXT 简历后生成。" /> : <section className="workspace-card"><div className="profile-status"><div><span className={`status-pill ${draft.confirmed ? "ready" : ""}`}>{draft.confirmed ? "已确认" : "待确认"}</span><h3>简历 v{draft.document_version}</h3></div><small>修改后重新确认会使相关岗位分析失效并重算。</small></div><div className="form-grid"><label className="field-stack"><span>学历</span><input value={draft.degree || ""} onChange={e => setDraft({...draft, degree:e.target.value})} /></label><label className="field-stack"><span>求职类型</span><input value={draft.job_type || ""} onChange={e => setDraft({...draft, job_type:e.target.value})} /></label>{list("target_directions", "目标方向（每行一个）")}{list("title_keywords", "岗位标题关键词")}{list("excluded_title_keywords", "排除关键词")}{list("skills", "已证实技能")}{list("project_evidence", "项目证据")}{list("supporting_skills", "辅助工程能力")}{list("learning_targets", "学习目标（不会当作已掌握技能）")}</div><button className="primary" onClick={() => run(() => api(`/api/career/profile/${draft.id}`, {method:"PUT", body:JSON.stringify({...draft, confirmed:true})}), "候选人画像已确认")}>确认画像</button></section>}
  </>;
}

function Jobs({ jobs, docs, profile, applications, run }: { jobs: Job[]; docs: Doc[]; profile: Profile | null; applications: Application[]; run: Runner }) {
  const [selectedDoc, setSelectedDoc] = useState(profile?.document_id || "");
  const [query, setQuery] = useState("");
  const [level, setLevel] = useState("");
  const [selected, setSelected] = useState<Job | null>(null);
  useEffect(() => { if (profile?.document_id) setSelectedDoc(profile.document_id); }, [profile]);
  const filtered = useMemo(() => jobs.filter(job => (!query || `${job.company} ${job.title}`.toLowerCase().includes(query.toLowerCase())) && (!level || job.latest_analysis?.evidence_level === level)), [jobs, query, level]);
  const submit = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); const data = Object.fromEntries(new FormData(event.currentTarget)); if (!data.source_url) delete data.source_url; run(() => api("/api/career/jobs", {method:"POST", body:JSON.stringify({...data, cohort:2027, recruitment_track:"campus", batch:"formal"})}), "岗位已保存"); event.currentTarget.reset(); };
  return <><PageHeading eyebrow="2027 CAMPUS JOBS" title="岗位情报" copy="先做校招范围硬筛选，再用简历事实形成要求—证据—缺口；没有百分制。" actions={<button className="ghost" onClick={() => setSelected({} as Job)}><Icon name="plus" size={14} /> 手动岗位</button>} />
    <div className="filter-bar"><label><Icon name="search" size={15} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="搜索公司或岗位" /></label><select value={level} onChange={e => setLevel(e.target.value)}><option value="">全部证据等级</option>{Object.entries(evidenceLabels).map(([key,value]) => <option key={key} value={key}>{value}</option>)}</select><select value={selectedDoc} onChange={e => setSelectedDoc(e.target.value)}><option value="">用于分析的简历</option>{docs.map(doc => <option key={doc.id} value={doc.id}>{doc.filename} · v{doc.version}</option>)}</select></div>
    {!profile?.confirmed && <div className="warning-banner"><Icon name="alert" /> 请先在“候选人画像”中核对并确认简历事实，之后才能生成岗位证据分析。</div>}
    <div className="jobs-layout"><div className="job-table"><div className="job-table-head"><span>公司 / 岗位</span><span>来源</span><span>JD</span><span>证据结论</span><span /></div>{filtered.map(job => <button className={`job-row ${selected?.id === job.id ? "selected" : ""}`} key={job.id} onClick={() => setSelected(job)}><span><b>{job.title}</b><small>{job.company}{job.city ? ` · ${job.city}` : ""}</small></span><span>{job.source_kind}</span><span className={`mini-state ${job.jd_status}`}>{job.jd_status === "complete" ? "完整" : "待补全"}</span><span className={`evidence-badge ${job.latest_analysis?.evidence_level || "pending"}`}>{job.latest_analysis?.label || "未分析"}</span><Icon name="chevron" size={15} /></button>)}</div>{selected?.id && <JobDetail job={selected} selectedDoc={selectedDoc} profileReady={Boolean(profile?.confirmed)} applications={applications} run={run} onClose={() => setSelected(null)} />}</div>
    {selected && !selected.id && <div className="modal-backdrop" onClick={() => setSelected(null)}><form className="modal-card form-grid" onSubmit={submit} onClick={e => e.stopPropagation()}><div className="modal-title"><h3>添加 2027 校招岗位</h3><button type="button" onClick={() => setSelected(null)}><Icon name="close" /></button></div><input name="company" placeholder="公司" required /><input name="title" placeholder="岗位" required /><input name="city" placeholder="城市（可选）" /><input name="source_url" placeholder="官方岗位链接（可选）" /><textarea name="description" placeholder="完整 JD" required /><button className="primary" type="submit">保存岗位</button></form></div>}
  </>;
}

function JobDetail({ job, selectedDoc, profileReady, applications, run, onClose }: { job: Job; selectedDoc: string; profileReady: boolean; applications: Application[]; run: Runner; onClose: () => void }) {
  const analysis = job.latest_analysis;
  return <aside className="detail-drawer"><div className="drawer-head"><div><span>{job.company}</span><h3>{job.title}</h3></div><button onClick={onClose}><Icon name="close" /></button></div><div className="drawer-actions"><button className="primary" disabled={!selectedDoc || !profileReady || job.jd_status !== "complete"} onClick={() => run(() => api(`/api/career/jobs/${job.id}/analysis`, {method:"POST", body:JSON.stringify({document_id:selectedDoc})}), "岗位证据分析已生成")}>生成证据分析</button>{!applications.some(a => a.job_id === job.id) && <button className="ghost" onClick={() => run(() => api("/api/career/applications", {method:"POST", body:JSON.stringify({job_id:job.id,status:"saved"})}), "已加入投递进度")}>加入投递</button>}{job.source_url && <button className="ghost" onClick={() => openCareerUrl(job.source_url!)}><Icon name="external" size={14} /> 官网</button>}</div><section><h4>岗位说明</h4><p className="jd-text">{job.description}</p></section>{analysis ? <AnalysisCard analysis={analysis} /> : <Empty title="尚未分析" copy="只有完整 JD 和已确认候选人画像才能生成证据结论。" compact />}</aside>;
}

function Companies({ sources, run }: { sources: Source[]; run: Runner }) {
  const submit = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); const data = Object.fromEntries(new FormData(event.currentTarget)); run(() => api("/api/career/companies", {method:"POST",body:JSON.stringify(data)}), "公司来源已添加"); event.currentTarget.reset(); };
  return <><PageHeading eyebrow="SOURCE HEALTH" title="公司来源" copy="维护官方校招入口和聚合来源；抓取只访问公开页面，不登录、不绕过验证码。" /><form className="workspace-card compact-form" onSubmit={submit}><input name="company" placeholder="公司" required /><input name="entry_url" type="url" placeholder="2027 校招入口" required /><select name="source_kind" defaultValue="official"><option value="official">官方招聘页</option><option value="offerbiu">OfferBiu</option><option value="manual">其它公开来源</option></select><button className="primary">添加来源</button></form><div className="source-grid">{sources.map(source => <article className="workspace-card" key={source.id}><div className="source-head"><div><span className={`health-dot ${source.status}`} /><h3>{source.company}</h3></div><span>{source.source_kind}</span></div><a href="#" onClick={e => {e.preventDefault(); openCareerUrl(source.entry_url);}}>{source.entry_url}</a><div className="source-stats"><span><b>{source.job_count}</b> 岗位</span><span><b>{source.incomplete_jd_count}</b> JD 待补全</span></div>{source.last_error && <p className="error-copy">{source.last_error}</p>}<button className="ghost" disabled={source.status === "running"} onClick={() => run(() => api(`/api/career/companies/${source.id}/crawl`, {method:"POST"}), "抓取任务已创建")}><Icon name="refresh" size={14} /> {source.status === "running" ? "抓取中" : "抓取公开岗位"}</button></article>)}</div></>;
}

function Applications({ applications, run }: { applications: Application[]; run: Runner }) {
  return <><PageHeading eyebrow="APPLICATION TRACKER" title="投递进度" copy="手工纠正允许任意阶段；邮件和官网复核必须确认，并保留来源证据。" /><div className="kanban">{statuses.map(status => <section className="kanban-column" key={status}><h3>{statusLabels[status]} <span>{applications.filter(a => a.status === status).length}</span></h3>{applications.filter(a => a.status === status).map(item => <ApplicationCard key={item.id} item={item} run={run} />)}</section>)}</div></>;
}

function ApplicationCard({ item, run }: { item: Application; run: Runner }) {
  const [events, setEvents] = useState<ApplicationEvent[] | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const toggle = async () => setEvents(events ? null : await api(`/api/career/applications/${item.id}/events`));
  const review = async () => {
    if (!window.feiDesktop) throw new Error("官网状态复核需要在 Fei 桌面应用内使用");
    setReviewing(true);
    try {
      const result = await window.feiDesktop.careerBrowser.reviewApplication({applicationId: item.id});
      if (result.blocked || !result.reviewId || !result.observedStatus) {
        throw new Error("当前页面需要登录、验证码或人工判断；本次没有修改投递状态");
      }
      const label = statusLabels[result.observedStatus] || result.observedStatus;
      if (!window.confirm(`官网页面识别为“${label}”，置信度 ${Math.round((result.confidence || 0) * 100)}%。\n\n确认后才会写入投递时间线，是否继续？`)) {
        throw new Error("已取消确认，投递状态保持不变");
      }
      await api(`/api/career/review-observations/${result.reviewId}/confirm`, {
        method: "POST",
        body: JSON.stringify({status: result.observedStatus, note: "用户在 Fei 内置浏览器中确认官网复核结果"}),
      });
    } finally {
      setReviewing(false);
    }
  };
  return <article><b>{item.job_title}</b><small>{item.company_name}</small><select value={item.status} onChange={e => run(() => api(`/api/career/applications/${item.id}`, {method:"PATCH",body:JSON.stringify({status:e.target.value})}), "投递状态已人工更正")}>{statuses.map(s => <option key={s} value={s}>{statusLabels[s]}</option>)}</select>{item.record_url && <><button className="timeline-toggle" onClick={() => openCareerUrl(item.record_url!, item.id)}>打开官网进度页</button><button className="timeline-toggle" disabled={reviewing} onClick={() => run(review, "官网复核结果已确认并写入时间线")}>{reviewing ? "正在读取当前页…" : "读取当前页并确认"}</button></>}<button className="timeline-toggle" onClick={() => void toggle()}>{events ? "收起时间线" : "查看时间线"}</button>{events && <ol className="timeline">{events.map(event => <li key={event.id}><b>{statusLabels[event.to_status] || event.to_status}</b><small>{event.source} · {new Date(event.created_at).toLocaleString()}</small>{event.note && <em>{event.note}</em>}</li>)}</ol>}</article>;
}

function Mail({ suggestions, applications, run }: { suggestions: Suggestion[]; applications: Application[]; run: Runner }) {
  return <><PageHeading eyebrow="READ-ONLY IMAP" title="招聘邮件" copy="通过 EXAMINE、UID 增量和 BODY.PEEK 读取；只保存求职摘要，建议确认前不会修改投递。" actions={<button className="primary" onClick={() => run(() => api("/api/career/mail/sync", {method:"POST"}), "只读同步任务已创建")}><Icon name="refresh" size={14} /> 同步邮件</button>} /><div className="record-list">{suggestions.length === 0 && <Empty title="没有待确认邮件" copy="非求职邮件分析后不会保存。" />}{suggestions.map(item => <MailCard key={item.id} item={item} applications={applications} run={run} />)}</div></>;
}

function MailCard({ item, applications, run }: { item: Suggestion; applications: Application[]; run: Runner }) {
  const [applicationId, setApplicationId] = useState(item.application_id || ""); const [status, setStatus] = useState(item.suggested_status || "");
  return <article className="workspace-card mail-card"><div><div className="mail-meta"><span>{item.mail_type}</span><span>{Math.round(item.confidence*100)}% 置信度</span></div><h3>{item.subject}</h3><small>{item.sender}</small><p>{item.body_summary}</p><em>{item.rationale}</em></div><div className="mail-confirm"><select value={applicationId} onChange={e => setApplicationId(e.target.value)}><option value="">选择关联投递</option>{applications.map(app => <option key={app.id} value={app.id}>{app.company_name} · {app.job_title}</option>)}</select><select value={status} onChange={e => setStatus(e.target.value)}><option value="">选择阶段</option>{statuses.map(value => <option key={value} value={value}>{statusLabels[value]}</option>)}</select><button className="primary" disabled={!applicationId || !status} onClick={() => run(() => api(`/api/career/mail/${item.id}/confirm`, {method:"POST",body:JSON.stringify({application_id:applicationId,status})}), "邮件建议已确认")}>确认并写入时间线</button></div></article>;
}

function Schedule({ items, applications, run }: { items: ScheduleItem[]; applications: Application[]; run: Runner }) {
  const submit = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); const data = Object.fromEntries(new FormData(event.currentTarget)); for (const key of Object.keys(data)) if (!data[key]) delete data[key]; run(() => api("/api/career/schedule", {method:"POST",body:JSON.stringify(data)}), "日程已创建"); event.currentTarget.reset(); };
  return <><PageHeading eyebrow="SCHEDULE" title="日程与待办" copy="明确开始时间进入日程，只有截止时间的事项保留截止提醒，时间未知则作为待办。" /><form className="workspace-card compact-form" onSubmit={submit}><input name="title" placeholder="事项" required /><select name="item_type"><option value="assessment">测评</option><option value="written">笔试</option><option value="interview">面试</option><option value="deadline">截止提醒</option><option value="todo">待办</option></select><select name="application_id"><option value="">不关联投递</option>{applications.map(app => <option key={app.id} value={app.id}>{app.company_name} · {app.job_title}</option>)}</select><input name="event_date" type="datetime-local" /><input name="deadline_at" type="datetime-local" /><button className="primary">添加</button></form><div className="schedule-list">{items.map(item => <article className="workspace-card" key={item.id}><span className="schedule-date">{item.event_date ? new Date(item.event_date).toLocaleString() : item.deadline_at ? `截止 ${new Date(item.deadline_at).toLocaleString()}` : "时间待定"}</span><div><h3>{item.title}</h3><p>{item.item_type} · {item.source}</p></div><span className="status-pill ready">{item.status}</span></article>)}</div></>;
}

function Interviews({ interviews, applications, run }: { interviews: Interview[]; applications: Application[]; run: Runner }) {
  const submit = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); const data = Object.fromEntries(new FormData(event.currentTarget)); for (const key of Object.keys(data)) if (!data[key]) delete data[key]; const app = applications.find(a => a.id === data.application_id); run(() => api("/api/interviews", {method:"POST",body:JSON.stringify({...data, job_id:app?.job_id, company:data.company || app?.company_name, job_title:data.job_title || app?.job_title})}), "面试记录已创建"); event.currentTarget.reset(); };
  return <><PageHeading eyebrow="INTERVIEW REVIEW" title="面试记录与复盘" copy="原始录音永久保存在 MinIO；转写必须编辑确认后才能生成逐题复盘。" /><form className="workspace-card compact-form" onSubmit={submit}><select name="application_id"><option value="">选择关联投递（可选）</option>{applications.map(app => <option key={app.id} value={app.id}>{app.company_name} · {app.job_title}</option>)}</select><input name="company" placeholder="公司（未关联时必填）" /><input name="job_title" placeholder="岗位" /><input name="scheduled_at" type="datetime-local" /><input name="round" placeholder="轮次" /><button className="primary">创建记录</button></form><div className="record-list">{interviews.map(item => <InterviewCard key={item.id} item={item} run={run} />)}</div></>;
}

function InterviewCard({ item, run }: { item: Interview; run: Runner }) {
  const [text, setText] = useState(item.transcript || ""); const [hotwords, setHotwords] = useState(""); useEffect(() => setText(item.transcript || ""), [item.transcript]);
  return <article className="workspace-card"><div className="interview-head"><div><span className="record-meta">{item.round || "未填写轮次"}{item.scheduled_at ? ` · ${new Date(item.scheduled_at).toLocaleString()}` : ""}</span><h3>{item.company}{item.job_title ? ` · ${item.job_title}` : ""}</h3></div><span className={`status-pill ${item.transcript_confirmed ? "ready" : ""}`}>{item.transcript_confirmed ? "文本已确认" : "待确认"}</span></div><textarea className="transcript" value={text} onChange={e => setText(e.target.value)} placeholder="转写或手动输入面试内容" /><input className="hotwords" value={hotwords} onChange={e => setHotwords(e.target.value)} placeholder="岗位技术词热词，用逗号分隔" /><div className="record-actions"><label className="file-button small"><Icon name="mic" size={14} /> 上传录音<input type="file" accept="audio/*,.m4a" onChange={e => e.target.files?.[0] && run(() => upload(`/api/interviews/${item.id}/audio`, e.target.files![0]), "录音已保存")} /></label>{item.audio_document_id && <button onClick={() => run(() => api(`/api/interviews/${item.id}/transcribe`, {method:"POST",body:JSON.stringify({language_hints:["zh","en"],vocabulary:hotwords.split(/[,，]/).map(x=>x.trim()).filter(Boolean),diarization:true})}), "转写任务已创建")}>开始转写</button>}<button disabled={!text} onClick={() => run(() => api(`/api/interviews/${item.id}/transcript`, {method:"PUT",body:JSON.stringify({transcript:text})}), "文本已确认")}>确认文本</button><button disabled={!item.transcript_confirmed} onClick={() => run(() => api(`/api/interviews/${item.id}/review`, {method:"POST"}), "复盘已生成")}>开始复盘</button></div>{item.latest_review && <ReviewCard review={item.latest_review.result} />}</article>;
}

function Automations({ items, tasks, run }: { items: Automation[]; tasks: Task[]; run: Runner }) {
  const submit = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); const data = Object.fromEntries(new FormData(event.currentTarget)); run(() => api("/api/career/automations", {method:"POST",body:JSON.stringify({...data,payload:{}})}), "自动化已创建"); event.currentTarget.reset(); };
  return <><PageHeading eyebrow="AUTOMATIONS" title="自动化与任务" copy="仅在 Fei 桌面软件运行时执行；错过的时间不会伪装成成功。" /><form className="workspace-card compact-form" onSubmit={submit}><input name="name" placeholder="自动化名称" required /><select name="task_kind"><option value="job_discovery">岗位发现</option><option value="mail_sync">邮件同步</option><option value="application_review">官网复核提醒</option></select><input name="schedule_time" type="time" required /><input name="timezone" defaultValue="Asia/Shanghai" /><button className="primary">创建</button></form><div className="automation-grid">{items.map(item => <article className="workspace-card" key={item.id}><div><span className={`status-pill ${item.enabled ? "ready" : ""}`}>{item.enabled ? "已启用" : "已暂停"}</span><h3>{item.name}</h3><p>{item.task_kind} · 每天 {item.schedule_time} · {item.timezone}</p>{item.last_error && <small className="error-copy">{item.last_error}</small>}</div><button className="ghost" onClick={() => run(() => api(`/api/career/automations/${item.id}/toggle`, {method:"POST"}), item.enabled ? "自动化已暂停" : "自动化已启用")}>{item.enabled ? "暂停" : "启用"}</button></article>)}</div><section className="workspace-card"><h3>持久任务</h3><TaskList tasks={tasks} /></section></>;
}

function AnalysisCard({ analysis }: { analysis: Analysis }) { return <section className="analysis-panel"><header><span className={`evidence-badge ${analysis.evidence_level}`}>{analysis.label}</span><small>简历 v{analysis.document_version} · {analysis.model}<br />{analysis.prompt_version} · {new Date(analysis.created_at).toLocaleString()}</small></header><p>{analysis.result.summary}</p><div className="evidence-table"><div className="evidence-head"><b>岗位要求</b><b>简历事实</b><b>关系</b></div>{analysis.result.evidence_table.map((row,index) => <div key={index}><span><small>{row.requirement_type}</small>{row.requirement}</span><span>{row.evidence || "未找到证据"}{row.source_quote && <q>{row.source_quote}</q>}</span><span className={`assessment ${row.assessment}`}>{row.assessment}</span></div>)}</div><div className="artifact-columns"><div><b>核心缺口</b><ul>{analysis.result.missing_core_requirements.map(x => <li key={x}>{x}</li>)}</ul></div><div><b>准备建议</b><ul>{analysis.result.preparation_actions.map(x => <li key={x}>{x}</li>)}</ul></div></div></section>; }
function ReviewCard({ review }: { review: Review }) { return <section className="analysis-panel"><header><b>面试复盘报告</b></header><p>{review.overview}</p>{review.answers.map((answer,index) => <details key={index}><summary>{answer.question}</summary><p>{answer.answer}</p><div className="artifact-columns"><div><b>优点</b><ul>{answer.strengths.map(x => <li key={x}>{x}</li>)}</ul></div><div><b>改进</b><ul>{answer.improvements.map(x => <li key={x}>{x}</li>)}</ul></div></div></details>)}</section>; }
function TaskList({ tasks }: { tasks: Task[] }) { return <div className="task-list">{tasks.length === 0 && <p>暂无任务</p>}{tasks.map(task => <div key={task.id}><span className={`task-state ${task.status}`}>{task.status}</span><b>{task.kind}</b><progress max="100" value={task.progress} /><small>{task.error || new Date(task.updated_at).toLocaleString()}</small></div>)}</div>; }
function Empty({ title, copy, compact=false }: { title: string; copy: string; compact?: boolean }) { return <div className={`empty-state ${compact ? "compact" : ""}`}><Icon name="file" /><b>{title}</b><p>{copy}</p></div>; }

type Runner = (work: () => Promise<unknown>, message: string) => Promise<void>;
function openCareerUrl(url: string, applicationId?: string) { const desktop = window.feiDesktop; if (desktop) void desktop.careerBrowser.open({url, applicationId}); else window.open(url, "_blank", "noopener,noreferrer"); }
