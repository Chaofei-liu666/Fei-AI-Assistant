"use client";

import { useState } from "react";
import { FeiAssistant } from "./FeiAssistant";
import { JobWorkspace } from "./JobWorkspace";
import { SettingsPanel } from "./SettingsPanel";

type View = "chat" | "job" | "settings";

export function AppShell() {
  const [view, setView] = useState<View>("chat");
  const [jobTab, setJobTab] = useState("overview");
  const title = view === "chat" ? "主对话" : view === "settings" ? "设置" : "求职工作区";
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark">F</span><div><strong>Fei</strong><span>智能助手</span></div></div>
      <nav className="nav-list" aria-label="功能模块">
        <p className="nav-label">工作空间</p>
        <button className={`nav-item ${view === "chat" ? "active" : ""}`} onClick={() => setView("chat")}><span>◎</span> 主对话</button>
        <button className={`nav-item ${view === "job" ? "active" : ""}`} onClick={() => setView("job")}><span>▤</span> 求职</button>
        <button className={`nav-item ${view === "settings" ? "active" : ""}`} onClick={() => setView("settings")}><span>⚙</span> 设置</button>
      </nav>
      {view === "job" && <div className="subnav">{[["overview","总览"],["jobs","岗位"],["applications","投递看板"],["mail","邮件"],["interviews","面试记录"],["assistant","求职对话"]].map(([id,label]) => <button key={id} className={jobTab === id ? "active" : ""} onClick={() => setJobTab(id)}>{label}</button>)}</div>}
      <div className="sidebar-footer"><span className="avatar">本</span><div><strong>本地单用户</strong><small>数据保存在你的设备</small></div></div>
    </aside>
    <main className="main-panel">
      <header className="topbar"><div><h1>{title}{view === "job" && <span className="module-tag">模块</span>}</h1><p><span className="online-dot" /> PostgreSQL · MinIO · LangGraph</p></div><div className="privacy-badge">仅绑定 127.0.0.1</div></header>
      {view === "chat" && <FeiAssistant module="general" />}
      {view === "job" && (jobTab === "assistant" ? <FeiAssistant module="job_search" /> : <JobWorkspace tab={jobTab} onTab={setJobTab} />)}
      {view === "settings" && <SettingsPanel />}
    </main>
  </div>;
}
