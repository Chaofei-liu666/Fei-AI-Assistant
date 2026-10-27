"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, upload } from "@/lib/api";

type Evidence = { requirement: string; evidence?: string; assessment: string; source_quote?: string };
type Job = { id: string; company: string; title: string; description: string; created_at: string; latest_analysis?: { match_level: string; model: string; document_version: number; result: { summary: string; evidence_table: Evidence[]; gaps: string[]; risks: string[]; preparation_actions: string[] } } };
type Application = { id: string; job_id: string; company: string; title: string; status: string };
type ApplicationEvent = { id: string; from_status?: string; to_status: string; source: string; note?: string; created_at: string };
type Suggestion = { id: string; subject: string; sender: string; body_summary: string; mail_type: string; application_id?: string; suggested_status?: string; confidence: number; rationale: string };
type Review = { overview: string; answers: { question: string; answer: string; strengths: string[]; missing_evidence: string[]; structure_issues: string[]; improvements: string[] }[]; practice_questions: string[] };
type Interview = { id: string; company: string; scheduled_at?: string; round?: string; outcome?: string; transcript?: string; transcript_confirmed: boolean; audio_document_id?: string; latest_review?: { result: Review; model: string } };
type Doc = { id: string; filename: string; version: number };
type Task = { id: string; kind: string; status: string; progress: number; error?: string; updated_at: string };

const statusLabels: Record<string, string> = { saved: "收藏", applied: "已投递", screening: "筛选中", assessment: "测评", interview: "面试", offer: "Offer", rejected: "拒绝", withdrawn: "撤回" };
const statuses = Object.keys(statusLabels);

export function JobWorkspace({ tab, onTab }: { tab: string; onTab: (tab: string) => void }) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [docs, setDocs] = useState<Doc[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [notice, setNotice] = useState("");
  const refresh = useCallback(async () => {
    const [j, a, m, i, d, t] = await Promise.all([
      api<Job[]>("/api/jobs"), api<Application[]>("/api/applications"),
      api<Suggestion[]>("/api/mail/suggestions"), api<Interview[]>("/api/interviews"), api<Doc[]>("/api/files?kind=resume"), api<Task[]>("/api/tasks?limit=10"),
    ]);
    setJobs(j); setApplications(a); setSuggestions(m); setInterviews(i); setDocs(d); setTasks(t);
  }, []);
  useEffect(() => { refresh().catch((error) => setNotice(error.message)); const timer = setInterval(() => refresh().catch(() => undefined), 5000); return () => clearInterval(timer); }, [refresh]);
  const run = async (work: () => Promise<unknown>, message: string) => { try { await work(); setNotice(message); await refresh(); } catch (error) { setNotice(error instanceof Error ? error.message : "操作失败"); } };

  return <div className="workspace-scroll">
    {notice && <div className="notice" onClick={() => setNotice("")}>{notice}</div>}
    {tab === "overview" && <Overview jobs={jobs} applications={applications} suggestions={suggestions} interviews={interviews} tasks={tasks} onTab={onTab} />}
    {tab === "jobs" && <Jobs jobs={jobs} docs={docs} applications={applications} run={run} />}
    {tab === "applications" && <Applications applications={applications} run={run} />}
    {tab === "mail" && <Mail suggestions={suggestions} applications={applications} run={run} />}
    {tab === "interviews" && <Interviews interviews={interviews} run={run} />}
  </div>;
}

function Overview({ jobs, applications, suggestions, interviews, tasks, onTab }: { jobs: Job[]; applications: Application[]; suggestions: Suggestion[]; interviews: Interview[]; tasks: Task[]; onTab: (tab: string) => void }) {
  const cards = [["岗位", jobs.length, "jobs"], ["进行中投递", applications.filter((a) => !["rejected","withdrawn"].includes(a.status)).length, "applications"], ["待确认邮件", suggestions.length, "mail"], ["面试记录", interviews.length, "interviews"]] as const;
  return <><div className="workspace-heading"><div><p className="eyebrow">JOB SEARCH</p><h2>求职总览</h2><p>模型负责分析，确定性服务负责状态、文件与同步。</p></div></div><div className="metric-grid">{cards.map(([label, value, target]) => <button className="metric-card" key={label} onClick={() => onTab(target)}><strong>{value}</strong><span>{label}</span></button>)}</div>{tasks.length > 0 && <section className="workspace-card"><h3>任务进度</h3><div className="task-list">{tasks.map((task) => <div key={task.id}><span className={`task-state ${task.status}`}>{task.status}</span><b>{task.kind}</b><progress max="100" value={task.progress} /><small>{task.error || new Date(task.updated_at).toLocaleString()}</small></div>)}</div></section>}<section className="workspace-card"><h3>明确的执行边界</h3><div className="boundary-grid"><p><b>自动完成</b><br />只读同步、文本提取、分析报告与任务恢复</p><p><b>必须确认</b><br />邮件建议引发的投递状态变化、面试转写文本</p><p><b>不会执行</b><br />发送/删除邮件、招聘网站投递、虚构或改写简历事实</p></div></section></>;
}

function Jobs({ jobs, docs, applications, run }: { jobs: Job[]; docs: Doc[]; applications: Application[]; run: (f: () => Promise<unknown>, m: string) => Promise<void> }) {
  const [selectedDoc, setSelectedDoc] = useState("");
  const submit = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); const data = Object.fromEntries(new FormData(event.currentTarget)); if (!data.source_url) delete data.source_url; if (!data.notes) delete data.notes; run(() => api("/api/jobs", { method: "POST", body: JSON.stringify(data) }), "岗位已保存"); event.currentTarget.reset(); };
  return <><div className="workspace-heading"><div><h2>岗位与证据分析</h2><p>分析保留模型、Prompt、简历版本和生成时间。</p></div><label className="file-button">上传简历<input type="file" accept=".pdf,.docx,.txt" onChange={(e) => e.target.files?.[0] && run(() => upload("/api/files?kind=resume", e.target.files![0]), "简历已上传")} /></label></div>
    <form className="workspace-card form-grid" onSubmit={submit}><input name="company" placeholder="公司" required /><input name="title" placeholder="职位" required /><input name="source_url" placeholder="来源链接（可选）" /><textarea name="description" placeholder="岗位 JD" required /><textarea name="notes" placeholder="备注（可选）" /><button className="primary" type="submit">保存岗位</button></form>
    <div className="toolbar"><select value={selectedDoc} onChange={(e) => setSelectedDoc(e.target.value)}><option value="">选择用于分析的简历</option>{docs.map((d) => <option key={d.id} value={d.id}>{d.filename} · v{d.version}</option>)}</select></div>
    <div className="record-list">{jobs.map((job) => <article className="workspace-card" key={job.id}><div className="record"><div><span className="record-meta">{job.company}</span><h3>{job.title}</h3><p>{job.description.slice(0, 180)}</p></div><div className="record-actions"><button disabled={!selectedDoc} onClick={() => run(() => api(`/api/jobs/${job.id}/analyze`, { method: "POST", body: JSON.stringify({ document_id: selectedDoc }) }), "岗位分析已生成")}>分析</button>{!applications.some((a) => a.job_id === job.id) && <button onClick={() => run(() => api("/api/applications", { method: "POST", body: JSON.stringify({ job_id: job.id, status: "saved" }) }), "已加入投递看板")}>加入看板</button>}</div></div>{job.latest_analysis && <AnalysisCard analysis={job.latest_analysis} />}</article>)}</div></>;
}

function Applications({ applications, run }: { applications: Application[]; run: (f: () => Promise<unknown>, m: string) => Promise<void> }) {
  return <><div className="workspace-heading"><div><h2>投递看板</h2><p>每次变化都会追加到事件时间线，不覆盖历史。</p></div></div><div className="kanban">{statuses.map((status) => <section className="kanban-column" key={status}><h3>{statusLabels[status]} <span>{applications.filter((a) => a.status === status).length}</span></h3>{applications.filter((a) => a.status === status).map((item) => <ApplicationCard key={item.id} item={item} run={run} />)}</section>)}</div></>;
}

function ApplicationCard({ item, run }: { item: Application; run: (f: () => Promise<unknown>, m: string) => Promise<void> }) {
  const [events, setEvents] = useState<ApplicationEvent[] | null>(null);
  const toggle = async () => { if (events) { setEvents(null); return; } setEvents(await api<ApplicationEvent[]>(`/api/applications/${item.id}/events`)); };
  return <article><b>{item.title}</b><small>{item.company}</small><select value={item.status} onChange={(e) => run(() => api(`/api/applications/${item.id}/status`, { method: "PATCH", body: JSON.stringify({ status: e.target.value }) }), "投递状态已更新")}>{statuses.map((s) => <option key={s} value={s}>{statusLabels[s]}</option>)}</select><button className="timeline-toggle" onClick={() => void toggle()}>{events ? "收起" : "时间线"}</button>{events && <ol className="timeline">{events.map((event) => <li key={event.id}><b>{statusLabels[event.to_status]}</b><small>{event.source} · {new Date(event.created_at).toLocaleString()}</small></li>)}</ol>}</article>;
}

function Mail({ suggestions, applications, run }: { suggestions: Suggestion[]; applications: Application[]; run: (f: () => Promise<unknown>, m: string) => Promise<void> }) {
  return <><div className="workspace-heading"><div><h2>163 邮件建议</h2><p>同步不会改变已读状态；任何状态建议都要确认。</p></div><button className="primary" onClick={() => run(() => api("/api/mail/sync", { method: "POST" }), "同步任务已创建")}>手动同步</button></div><div className="record-list">{suggestions.length === 0 && <Empty text="暂无待确认邮件" />}{suggestions.map((item) => <MailCard key={item.id} item={item} applications={applications} run={run} />)}</div></>;
}

function MailCard({ item, applications, run }: { item: Suggestion; applications: Application[]; run: (f: () => Promise<unknown>, m: string) => Promise<void> }) {
  const [applicationId, setApplicationId] = useState(item.application_id || "");
  const [status, setStatus] = useState(item.suggested_status || "");
  return <article className="workspace-card record"><div><span className="record-meta">{item.mail_type} · 置信度 {Math.round(item.confidence * 100)}%</span><h3>{item.subject}</h3><p>{item.sender}</p><p>{item.body_summary}</p><small>{item.rationale}</small></div><div className="mail-confirm"><select value={applicationId} onChange={(e) => setApplicationId(e.target.value)}><option value="">手工选择关联岗位</option>{applications.map((app) => <option key={app.id} value={app.id}>{app.company} · {app.title}</option>)}</select><select value={status} onChange={(e) => setStatus(e.target.value)}><option value="">选择建议状态</option>{statuses.map((value) => <option key={value} value={value}>{statusLabels[value]}</option>)}</select><button className="primary" disabled={!applicationId || !status} onClick={() => run(() => api(`/api/mail/suggestions/${item.id}/confirm`, { method: "POST", body: JSON.stringify({ application_id: applicationId, status }) }), "建议已确认并写入事件")}>确认更新</button></div></article>;
}

function Interviews({ interviews, run }: { interviews: Interview[]; run: (f: () => Promise<unknown>, m: string) => Promise<void> }) {
  const submit = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); const data = Object.fromEntries(new FormData(event.currentTarget)); for (const key of Object.keys(data)) if (!data[key]) delete data[key]; run(() => api("/api/interviews", { method: "POST", body: JSON.stringify(data) }), "面试记录已创建"); event.currentTarget.reset(); };
  return <><div className="workspace-heading"><div><h2>面试记录与复盘</h2><p>录音转写后必须编辑并确认，才能开始复盘。</p></div></div><form className="workspace-card form-grid" onSubmit={submit}><input name="company" placeholder="公司" required /><input name="scheduled_at" type="datetime-local" aria-label="面试时间" /><input name="round" placeholder="轮次" /><input name="outcome" placeholder="结果" /><textarea name="transcript" placeholder="可直接粘贴面试内容" /><button className="primary" type="submit">创建记录</button></form><div className="record-list">{interviews.map((item) => <InterviewCard key={item.id} item={item} run={run} />)}</div></>;
}

function InterviewCard({ item, run }: { item: Interview; run: (f: () => Promise<unknown>, m: string) => Promise<void> }) {
  const [text, setText] = useState(item.transcript ?? "");
  const [hotwords, setHotwords] = useState("");
  useEffect(() => setText(item.transcript ?? ""), [item.transcript]);
  return <article className="workspace-card"><span className="record-meta">{item.round || "未填写轮次"}{item.outcome ? ` · ${item.outcome}` : ""}{item.scheduled_at ? ` · ${new Date(item.scheduled_at).toLocaleString()}` : ""}</span><h3>{item.company}</h3><textarea className="transcript" value={text} onChange={(e) => setText(e.target.value)} placeholder="转写或手动输入内容" /><input className="hotwords" value={hotwords} onChange={(e) => setHotwords(e.target.value)} placeholder="岗位技术词热词，用逗号分隔" /><div className="record-actions"><label className="file-button small">上传录音<input type="file" accept="audio/*,.m4a" onChange={(e) => e.target.files?.[0] && run(() => upload(`/api/interviews/${item.id}/audio`, e.target.files![0]), "录音已保存到 MinIO")} /></label>{item.audio_document_id && <button onClick={() => run(() => api(`/api/interviews/${item.id}/transcribe`, { method: "POST", body: JSON.stringify({ language_hints: ["zh","en"], vocabulary: hotwords.split(/[,，]/).map((word) => word.trim()).filter(Boolean), diarization: true }) }), "转写任务已创建")}>开始转写（中英/说话人分离）</button>}<button disabled={!text} onClick={() => run(() => api(`/api/interviews/${item.id}/transcript`, { method: "PUT", body: JSON.stringify({ transcript: text }) }), "文本已确认")}>确认文本</button><button disabled={!item.transcript_confirmed} onClick={() => run(() => api(`/api/interviews/${item.id}/review`, { method: "POST" }), "复盘报告已生成")}>开始复盘</button></div>{item.latest_review && <ReviewCard review={item.latest_review.result} />}</article>;
}

function AnalysisCard({ analysis }: { analysis: NonNullable<Job["latest_analysis"]> }) { return <section className="artifact-card"><header><b>岗位分析 Artifact</b><span>{analysis.match_level.toUpperCase()} · 简历 v{analysis.document_version} · {analysis.model}</span></header><p>{analysis.result.summary}</p><div className="evidence-table"><div className="evidence-head"><b>要求</b><b>简历证据</b><b>判断</b></div>{analysis.result.evidence_table.map((row, index) => <div key={index}><span>{row.requirement}</span><span>{row.evidence || "未找到证据"}</span><span className={`assessment ${row.assessment}`}>{row.assessment}</span></div>)}</div><div className="artifact-columns"><div><b>主要缺口</b><ul>{analysis.result.gaps.map((x) => <li key={x}>{x}</li>)}</ul></div><div><b>准备建议</b><ul>{analysis.result.preparation_actions.map((x) => <li key={x}>{x}</li>)}</ul></div></div></section>; }
function ReviewCard({ review }: { review: Review }) { return <section className="artifact-card"><header><b>面试复盘报告</b></header><p>{review.overview}</p>{review.answers.map((answer, index) => <details key={index}><summary>{answer.question}</summary><p>{answer.answer}</p><div className="artifact-columns"><div><b>优点</b><ul>{answer.strengths.map((x) => <li key={x}>{x}</li>)}</ul></div><div><b>改进</b><ul>{answer.improvements.map((x) => <li key={x}>{x}</li>)}</ul></div></div></details>)}</section>; }

function Empty({ text }: { text: string }) { return <div className="empty-state">{text}</div>; }
