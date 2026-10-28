"use client";

import { useEffect, useState } from "react";
import { FeiAssistant } from "./FeiAssistant";
import { HouseholdWorkspace } from "./HouseholdWorkspace";
import { JobWorkspace } from "./JobWorkspace";
import { RunsWorkspace } from "./RunsWorkspace";
import { SettingsPanel } from "./SettingsPanel";
import { threads } from "@/lib/threads";
import { AgentsWorkspace } from "./AgentsWorkspace";
import { ThreadList } from "./ThreadList";
import { TodayWorkspace } from "./TodayWorkspace";
import { Icon, type IconName } from "./Icon";

type View = "today" | "chat" | "agents" | "job" | "items" | "runs" | "settings";

const careerNav: [string, string, IconName, string][] = [
  ["overview", "概览", "dashboard", "今天需要关注的事项"],
  ["profile", "候选人画像", "file", "简历事实与求职方向"],
  ["jobs", "2027 校招岗位", "target", "岗位池与证据分析"],
  ["companies", "公司来源", "server", "招聘入口与抓取状态"],
  ["applications", "投递进度", "columns", "阶段和证据时间线"],
  ["schedule", "日程与待办", "clock", "面试、笔试和截止时间"],
  ["interviews", "面试复盘", "mic", "录音、转写与逐题建议"],
  ["automations", "自动化", "refresh", "计划任务与运行记录"],
  ["assistant", "求职 Agent", "sparkles", "和 Specialist 协作"],
];

const primaryNav: [View, string, IconName][] = [
  ["chat", "主对话", "chat"],
  ["today", "今天", "dashboard"],
  ["agents", "Agents", "sparkles"],
  ["runs", "运行记录", "clock"],
];

export function AppShell() {
  const [view, setView] = useState<View>("chat");
  const [jobTab, setJobTab] = useState("overview");

  useEffect(() => {
    const requested = new URLSearchParams(window.location.search).get("view");
    const allowed: View[] = ["chat", "today", "agents", "runs", "items", "job", "settings"];
    if (requested && (allowed as string[]).includes(requested)) setView(requested as View);
  }, []);
  const current = careerNav.find(([id]) => id === jobTab);
  const title = view === "job" ? current?.[1] : view === "today" ? "今天" : view === "chat" ? "主对话" : view === "agents" ? "Agents" : view === "items" ? "物品清单" : view === "runs" ? "运行记录" : "设置";

  const navigate = (target: string) => {
    const [next, tab] = target.split("/");
    if (next === "items" || next === "runs" || next === "chat" || next === "today" || next === "agents") { setView(next as View); return; }
    setView("job");
    if (tab) setJobTab(tab);
  };

  return <div className="product-shell">
    <aside className="context-sidebar">
      <div className="context-brand"><div><strong>Fei</strong><span>Intelligence workspace</span></div><span className="desktop-chip">LOCAL</span></div>

      {view === "job" ? <>
        <button className="side-back" onClick={() => setView("chat")}><Icon name="chevron" size={14} /> 返回对话</button>
        <div className="context-title"><p>CAREER</p><h2>求职工作台</h2></div>
        <nav className="context-nav">{careerNav.map(([id, label, icon]) => <button key={id} className={jobTab === id ? "active" : ""} onClick={() => setJobTab(id)}><Icon name={icon} size={16} /><span>{label}</span></button>)}</nav>
      </> : <>
        <button className="new-session" onClick={() => { threads.setActive(null); setView("chat"); }}><Icon name="plus" size={15} /> 新对话 <kbd>Ctrl N</kbd></button>
        <nav className="side-nav">
          {primaryNav.map(([id, label, icon]) => <button key={id} className={view === id ? "active" : ""} onClick={() => setView(id)}>
            <Icon name={icon} size={17} /><span>{label}</span>
            {id === "today" && <em />}
          </button>)}
        </nav>
        <p className="side-label">最近</p>
        <ThreadList onOpen={() => setView("chat")} />
      </>}

      <div className="side-bottom">
        {view !== "job" && <div className="side-hint">
          <p>工作方式</p>
          <div><span className="status-orb" /><small>LangGraph Orchestrator 在线</small></div>
          <div><span className="status-orb amber" /><small>写入操作需要你确认</small></div>
        </div>}
        <button className={`side-settings ${view === "settings" ? "active" : ""}`} onClick={() => setView("settings")}>
          <Icon name="settings" size={17} /><span>设置</span>
        </button>
        <div className="context-footer"><div><span className="status-orb" /><b>Local services</b></div><small>127.0.0.1 · 私有工作区</small></div>
      </div>
    </aside>

    <main className="workspace-main">
      <header className="workspace-topbar">
        <div><h1>{title}</h1></div>
        <button className="command-trigger"><Icon name="search" size={14} /><span>搜索或运行命令</span><kbd>Ctrl K</kbd></button>
        <div className="topbar-actions"><span className="system-state"><i /> 全部服务正常</span><button aria-label="通知"><Icon name="alert" size={16} /></button></div>
      </header>
      <div className="workspace-body">
        {view === "today" && <TodayWorkspace onNavigate={navigate} />}
        {view === "chat" && <FeiAssistant module="general" onNavigate={navigate} />}
        {view === "agents" && <AgentsWorkspace onNavigate={navigate} />}
        {view === "items" && <HouseholdWorkspace />}
        {view === "runs" && <RunsWorkspace />}
        {view === "job" && (jobTab === "assistant" ? <FeiAssistant module="job_search" onNavigate={navigate} /> : <JobWorkspace tab={jobTab} onTab={setJobTab} />)}
        {view === "settings" && <SettingsPanel />}
      </div>
    </main>
  </div>;
}
