"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Icon, type IconName } from "./Icon";
import styles from "./TodayWorkspace.module.css";

type InboxItem = {
  kind: string;
  severity: "action" | "info";
  title: string;
  detail: string;
  target: string;
  created_at: string | null;
};

type Inbox = { count: number; actions: InboxItem[]; notes: InboxItem[] };
type AgentCard = { id: string; title: string; description: string; target: string };

const kindIcon: Record<string, IconName> = {
  profile: "file",
  task: "alert",
  mail: "mail",
  household: "box",
  application: "columns",
};

const kindLabel: Record<string, string> = {
  profile: "求职 · 画像",
  task: "后台任务",
  mail: "邮件",
  household: "物品",
  application: "投递",
};

function when(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function TodayWorkspace({ onNavigate }: { onNavigate: (target: string) => void }) {
  const [data, setData] = useState<Inbox | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [agents, setAgents] = useState<AgentCard[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await api<Inbox>("/api/inbox"));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    void api<AgentCard[]>("/api/agents").then(setAgents).catch(() => {});
  }, [load]);

  const now = new Date();
  const dateLabel = now.toLocaleDateString("zh-CN", { month: "long", day: "numeric", weekday: "long" });
  const actions = data?.actions ?? [];
  const notes = data?.notes ?? [];
  const empty = data !== null && data.count === 0;

  return <div className="workspace-scroll">
    <header className={styles.hero}>
      <div className={styles.heroText}>
        <p className={styles.eyebrow}>TODAY · {dateLabel}</p>
        <h1>{actions.length > 0 ? `${actions.length} 件需要你处理` : "今天没有等你的事"}</h1>
        <p className={styles.sub}>邮件自动更新、后台任务和物品库存的变化都汇总在这里，不用逐个页面翻。</p>
      </div>
      <div className={styles.heroActions}>
        <button className={styles.ghost} onClick={() => void load()} disabled={loading}>
          <Icon name="refresh" size={15} /> {loading ? "刷新中" : "刷新"}
        </button>
        <button className={styles.primary} onClick={() => onNavigate("chat")}>
          <Icon name="sparkles" size={15} /> 问一句
        </button>
      </div>
    </header>

    {error && <div className={styles.alert}><Icon name="alert" size={15} /> {error}</div>}

    {!empty && <div className={styles.metaRow}>
      <span><b>{actions.length}</b> 待你处理</span>
      <span><b>{notes.length}</b> 最近变化</span>
      <span><b>{notes.filter((item) => item.kind === "household").length}</b> 低库存</span>
    </div>}

    {empty && <section className={styles.empty}>
      <span className={styles.emptyIcon}><Icon name="check" size={22} /></span>
      <h2>没有待处理的事</h2>
      <p>可以让 Fei 做点什么：整理简历、记一件家里的东西，或者查一份岗位。</p>
      <div className={styles.emptyActions}>
        <button className={styles.primary} onClick={() => onNavigate("chat")}>打开对话</button>
        <button className={styles.ghost} onClick={() => onNavigate("items")}>记一件物品</button>
      </div>
    </section>}

    {!empty && <div className={`${styles.grid} ${actions.length === 0 ? styles.single : ""}`}>
      {actions.length > 0 && <section className={styles.panel}>
        <header className={styles.panelHead}>
          <h2>需要你处理</h2>
          <span>{actions.length}</span>
        </header>
        <div className={styles.rows}>
          {actions.map((item, index) => <button key={`${item.kind}-${index}`} className={styles.row} onClick={() => onNavigate(item.target)}>
            <span className={`${styles.tile} ${styles.tileAction}`}>
              <Icon name={kindIcon[item.kind] || "alert"} size={17} />
            </span>
            <span className={styles.body}>
              <b>{item.title}</b>
              <small>{item.detail}</small>
            </span>
            <span className={styles.meta}>
              <small>{kindLabel[item.kind] || item.kind}</small>
              <small>{when(item.created_at)}</small>
            </span>
            <Icon name="chevron" size={16} />
          </button>)}
        </div>
      </section>}

      <aside className={styles.panel}>
        <header className={styles.panelHead}>
          <h2>最近变化</h2>
          <span>{notes.length}</span>
        </header>
        {notes.length === 0 && <p className={styles.placeholder}>最近没有自动更新。</p>}
        <div className={styles.rows}>
          {notes.map((item, index) => <button key={`${item.kind}-n-${index}`} className={styles.row} onClick={() => onNavigate(item.target)}>
            <span className={styles.tile}>
              <Icon name={kindIcon[item.kind] || "sparkles"} size={16} />
            </span>
            <span className={styles.body}>
              <b>{item.title}</b>
              <small>{item.detail}</small>
            </span>
            <span className={styles.meta}>
              <small>{when(item.created_at)}</small>
            </span>
          </button>)}
        </div>
      </aside>
    </div>}

    {agents.length > 0 && <section className={styles.agents}>
      <div className={styles.agentsGrid}>
        {agents.map((agent) => <button key={agent.id} className={styles.agentCard}
          onClick={() => onNavigate(agent.target)}>
          <span className={styles.agentTop}>
            <b>{agent.title}</b>
            <Icon name="arrow" size={15} />
          </span>
          <small>{agent.description}</small>
        </button>)}
        <button className={styles.agentCard} onClick={() => onNavigate("runs")}>
          <span className={styles.agentTop}>
            <b>运行记录</b>
            <Icon name="arrow" size={15} />
          </span>
          <small>每一次执行的计划、工具调用与结果</small>
        </button>
      </div>
    </section>}
  </div>;
}
