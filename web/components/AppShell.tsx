"use client";

import { useState } from "react";
import { FeiAssistant } from "./FeiAssistant";
import { HouseholdWorkspace } from "./HouseholdWorkspace";
import { JobWorkspace } from "./JobWorkspace";
import { RunsWorkspace } from "./RunsWorkspace";
import { SettingsPanel } from "./SettingsPanel";
import { Icon, type IconName } from "./Icon";

type View = "chat" | "job" | "items" | "runs" | "settings";
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

export function AppShell() {
  const [view, setView] = useState<View>("chat");
  const [jobTab, setJobTab] = useState("overview");
  const current = careerNav.find(([id]) => id === jobTab);
  const title = view === "job" ? current?.[1] : view === "chat" ? "Fei" : view === "items" ? "物品清单" : view === "runs" ? "运行记录" : "设置";
  const subtitle = view === "job" ? current?.[3] : view === "chat" ? "你的本地智能工作空间" : view === "items" ? "用一句话记录家里的东西放在哪" : view === "runs" ? "每一次执行的过程与结果" : "模型、语音、邮箱与本地环境";

  return <div className="product-shell">
    <aside className="app-rail">
      <button className="rail-logo" aria-label="Fei 首页" onClick={() => setView("chat")}>F</button>
      <div className="rail-nav">
        <RailButton label="主对话" icon="chat" active={view === "chat"} onClick={() => setView("chat")} />
        <RailButton label="求职工作台" icon="briefcase" active={view === "job"} onClick={() => setView("job")} />
        <RailButton label="物品清单" icon="box" active={view === "items"} onClick={() => setView("items")} />
        <RailButton label="运行记录" icon="clock" active={view === "runs"} onClick={() => setView("runs")} />
      </div>
      <div className="rail-bottom">
        <RailButton label="设置" icon="settings" active={view === "settings"} onClick={() => setView("settings")} />
        <span className="local-avatar" title="本地单用户">LC</span>
      </div>
    </aside>

    <aside className="context-sidebar">
      <div className="context-brand"><div><strong>Fei</strong><span>Intelligence workspace</span></div><span className="desktop-chip">LOCAL</span></div>
      {view === "job" ? <>
        <div className="context-title"><p>CAREER WORKSPACE</p><h2>求职工作台</h2></div>
        <nav className="context-nav">{careerNav.map(([id,label,icon]) => <button key={id} className={jobTab === id ? "active" : ""} onClick={() => setJobTab(id)}><Icon name={icon} size={16} /><span>{label}</span>{id === "mail" && <i />}</button>)}</nav>
      </> : view === "chat" ? <>
        <div className="context-title"><p>ASSISTANT</p><h2>主对话</h2></div>
        <button className="new-session"><Icon name="plus" size={15} /> 新对话 <kbd>Ctrl N</kbd></button>
        <div className="context-section"><p>可用模块</p><button onClick={() => {setView("job");setJobTab("assistant");}}><span className="module-glyph"><Icon name="briefcase" size={15} /></span><div><b>求职 Agent</b><small>5 个 Specialist</small></div><Icon name="chevron" size={14} /></button></div>
        <div className="context-section recent"><p>工作方式</p><div><span className="status-orb" /><small>LangGraph Orchestrator 在线</small></div><div><span className="status-orb amber" /><small>写入操作需要确认</small></div></div>
      </> : view === "items" ? <>
        <div className="context-title"><p>HOUSEHOLD</p><h2>物品清单</h2></div>
        <button className="new-session"><Icon name="plus" size={15} /> 记一件 <kbd>Ctrl N</kbd></button>
        <div className="context-section"><p>怎么用</p><button onClick={() => setView("chat")}><span className="module-glyph"><Icon name="sparkles" size={15} /></span><div><b>说一句话</b><small>「洗衣液放衣柜第二层」</small></div><Icon name="chevron" size={14} /></button></div>
        <div className="context-section recent"><p>规则</p><div><span className="status-orb" /><small>解析结果需你确认后才保存</small></div><div><span className="status-orb amber" /><small>位置按路径分层，可查可回溯</small></div></div>
      </> : view === "runs" ? <>
        <div className="context-title"><p>RUNS</p><h2>运行记录</h2></div>
        <div className="context-section"><p>看什么</p><div><span className="status-orb" /><small>计划、委派、工具调用与结果</small></div><div><span className="status-orb amber" /><small>失败会单独成行</small></div></div>
      </> : <>
        <div className="context-title"><p>PREFERENCES</p><h2>设置</h2></div>
        <nav className="context-nav"><button className="active"><Icon name="sparkles" size={16} /><span>模型与服务</span></button><button><Icon name="lock" size={16} /><span>隐私与凭据</span></button><button><Icon name="server" size={16} /><span>本地基础设施</span></button></nav>
      </>}
      <div className="context-footer"><div><span className="status-orb" /><b>Local services</b></div><small>127.0.0.1 · 私有工作区</small></div>
    </aside>

    <main className="workspace-main">
      <header className="workspace-topbar"><div><h1>{title}</h1><p>{subtitle}</p></div><button className="command-trigger"><Icon name="search" size={14} /><span>搜索或运行命令</span><kbd>Ctrl K</kbd></button><div className="topbar-actions"><span className="system-state"><i /> 全部服务正常</span><button aria-label="通知"><Icon name="alert" size={16} /></button></div></header>
      <div className="workspace-body">
        {view === "chat" && <FeiAssistant module="general" />}
        {view === "items" && <HouseholdWorkspace />}
        {view === "runs" && <RunsWorkspace />}
        {view === "job" && (jobTab === "assistant" ? <FeiAssistant module="job_search" /> : <JobWorkspace tab={jobTab} onTab={setJobTab} />)}
        {view === "settings" && <SettingsPanel />}
      </div>
    </main>
  </div>;
}

function RailButton({ label, icon, active, onClick }: { label: string; icon: IconName; active: boolean; onClick: () => void }) {
  return <button className={active ? "active" : ""} aria-label={label} title={label} onClick={onClick}><Icon name={icon} size={19} /></button>;
}
