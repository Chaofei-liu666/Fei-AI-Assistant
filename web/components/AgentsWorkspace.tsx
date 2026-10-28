"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Icon } from "./Icon";
import styles from "./AgentsWorkspace.module.css";

type AgentRow = {
  id: string;
  title: string;
  description: string;
  page: string;
  surface: "workspace" | "inline";
  target: string | null;
  tools: string[];
};

export function AgentsWorkspace({ onNavigate }: { onNavigate: (target: string) => void }) {
  const [agents, setAgents] = useState<AgentRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<{ id: string; title: string; customized: boolean } | null>(null);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);

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
        <h1>子 Agent</h1>
      </div>
      <span className={styles.count}>{agents.length} 个</span>
    </header>

    {error && <div className={styles.error}><Icon name="alert" size={15} /> {error}</div>}

    <div className={styles.grid}>
      {agents.map((agent) => {
        const workspace = agent.surface === "workspace" && agent.target;
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
            <button className={styles.linkButton} onClick={() => void openPrompt(agent)}>提示词</button>
          </div>
        </article>;
      })}
      {agents.length === 0 && !error && <p className={styles.empty}>还没有注册任何 Agent。</p>}
    </div>

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
