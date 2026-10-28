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
          </div>
        </article>;
      })}
      {agents.length === 0 && !error && <p className={styles.empty}>还没有注册任何 Agent。</p>}
    </div>

  </div>;
}
