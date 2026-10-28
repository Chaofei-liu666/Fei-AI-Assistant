"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Icon } from "./Icon";
import styles from "./AgentsWorkspace.module.css";

type SkillRow = {
  skill_id: string;
  title: string;
  description: string;
  prompt: string;
  tools: string[];
  enabled: boolean;
  builtin: boolean;
};

type AgentRow = {
  id: string;
  title: string;
  description: string;
  page: string;
  has_workspace: boolean;
  target: string | null;
  tools: string[];
};

export function AgentsWorkspace({ onNavigate }: { onNavigate: (target: string) => void }) {
  const [agents, setAgents] = useState<AgentRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<{ id: string; title: string; customized: boolean } | null>(null);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [skillsFor, setSkillsFor] = useState<{ id: string; title: string } | null>(null);
  const [skills, setSkills] = useState<SkillRow[]>([]);
  const [openSkill, setOpenSkill] = useState<string | null>(null);
  const [skillDraft, setSkillDraft] = useState<{ description: string; prompt: string; enabled: boolean } | null>(null);
  const [savingSkill, setSavingSkill] = useState(false);

  const openPrompt = async (agent: AgentRow) => {
    try {
      const data = await api<{ prompt: string; customized: boolean }>(`/api/agents/${agent.id}/prompt`);
      setEditing({ id: agent.id, title: agent.title, customized: data.customized });
      setDraft(data.prompt);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const savePrompt = async () => {
    if (!editing) return;
    setSaving(true);
    try {
      const data = await api<{ customized: boolean }>(`/api/agents/${editing.id}/prompt`, {
        method: "PUT",
        body: JSON.stringify({ prompt: draft }),
      });
      setEditing({ ...editing, customized: data.customized });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  const resetPrompt = async () => {
    if (!editing) return;
    setSaving(true);
    try {
      const data = await api<{ prompt: string; customized: boolean }>(`/api/agents/${editing.id}/prompt`, { method: "DELETE" });
      setDraft(data.prompt);
      setEditing({ ...editing, customized: data.customized });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  const openSkills = async (agent: AgentRow) => {
    try {
      const rows = await api<SkillRow[]>(`/api/agents/${agent.id}/skills`);
      setSkillsFor({ id: agent.id, title: agent.title });
      setSkills(rows);
      setOpenSkill(null);
      setSkillDraft(null);
      setEditing(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const selectSkill = (row: SkillRow) => {
    setOpenSkill(row.skill_id);
    setSkillDraft({ description: row.description, prompt: row.prompt, enabled: row.enabled });
  };

  const saveSkill = async () => {
    if (!skillsFor || !openSkill || !skillDraft) return;
    setSavingSkill(true);
    try {
      const updated = await api<SkillRow>(`/api/agents/${skillsFor.id}/skills/${openSkill}`, {
        method: "PUT",
        body: JSON.stringify(skillDraft),
      });
      setSkills(skills.map((row) => (row.skill_id === updated.skill_id ? updated : row)));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSavingSkill(false);
    }
  };

  useEffect(() => {
    let alive = true;
    api<AgentRow[]>("/api/agents")
      .then((rows) => { if (alive) setAgents(rows); })
      .catch((err) => { if (alive) setError(String(err.message || err)); });
    return () => { alive = false; };
  }, []);

  return <div className="workspace-scroll">
    <header className={styles.head}>
      <div>
        <p className={styles.eyebrow}>AGENTS</p>
        <h1>Agents</h1>
      </div>
      <span className={styles.count}>{agents.length} 个</span>
    </header>

    {error && <div className={styles.error}><Icon name="alert" size={15} /> {error}</div>}

    <div className={styles.grid}>
      {agents.map((agent) => {
        const workspace = agent.has_workspace && agent.target;
        return <article key={agent.id} className={styles.card}>
          <div className={styles.cardTop}>
            <span className={styles.badge}>{workspace ? "有工作区" : "仅在对话中"}</span>
            <span className={styles.tools}>{agent.tools.length} 个工具</span>
          </div>
          <h2>{agent.title}</h2>
          <p>{agent.description}</p>
          <div className={styles.actions}>
            {workspace
              ? <button className={styles.primary} onClick={() => onNavigate(agent.target as string)}>打开工作区</button>
              : <button className={styles.ghost} onClick={() => onNavigate("chat")}>在对话里调用</button>}
            <button className={styles.linkButton} onClick={() => void openPrompt(agent)}>Prompt</button>
            <button className={styles.linkButton} onClick={() => void openSkills(agent)}>Skills</button>
          </div>
        </article>;
      })}
      {agents.length === 0 && !error && <p className={styles.empty}>还没有注册任何 Agent。</p>}
    </div>

    {skillsFor && <section className={styles.editor}>
      <div className={styles.editorHead}>
        <h2>{skillsFor.title} · Skills</h2>
        <button className={styles.linkButton} onClick={() => setSkillsFor(null)}>关闭</button>
      </div>
      <div className={styles.skillList}>
        {skills.map((row) => <div key={row.skill_id} className={styles.skill}>
          <button className={styles.skillHead} onClick={() => selectSkill(row)}>
            <span>{row.title}</span>
            <span className={styles.tools}>{row.tools.length} tools · {row.enabled ? "启用" : "停用"}</span>
          </button>
          {openSkill === row.skill_id && skillDraft && <div className={styles.skillBody}>
            <label className={styles.field}>
              <span>Description</span>
              <input value={skillDraft.description} onChange={(event) => setSkillDraft({ ...skillDraft, description: event.target.value })} />
            </label>
            <label className={styles.field}>
              <span>Prompt</span>
              <textarea className={styles.textarea} rows={7} value={skillDraft.prompt} onChange={(event) => setSkillDraft({ ...skillDraft, prompt: event.target.value })} />
            </label>
            <div className={styles.actions}>
              <button className={styles.primary} onClick={() => void saveSkill()} disabled={savingSkill}>保存</button>
              <label className={styles.toggle}>
                <input type="checkbox" checked={skillDraft.enabled} onChange={(event) => setSkillDraft({ ...skillDraft, enabled: event.target.checked })} /> 启用
              </label>
            </div>
          </div>}
        </div>)}
        {skills.length === 0 && <p className={styles.empty}>这个 Agent 还没有 Skill。</p>}
      </div>
    </section>}
    {editing && <section className={styles.editor}>
      <div className={styles.editorHead}>
        <h2>{editing.title} · 系统提示词</h2>
        <span className={styles.badge}>{editing.customized ? "自定义" : "默认"}</span>
      </div>
      <textarea
        className={styles.textarea}
        rows={9}
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
      />
      <div className={styles.actions}>
        <button className={styles.primary} onClick={() => void savePrompt()} disabled={saving}>保存</button>
        <button className={styles.ghost} onClick={() => void resetPrompt()} disabled={saving}>恢复默认</button>
        <button className={styles.ghost} onClick={() => setEditing(null)}>关闭</button>
      </div>
    </section>}
  </div>;
}
