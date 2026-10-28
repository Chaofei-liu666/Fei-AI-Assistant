"use client";

import { useCallback, useEffect, useState } from "react";
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

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/inbox");
      if (!response.ok) throw new Error(response.statusText);
      setData(await response.json() as Inbox);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const today = new Date().toLocaleDateString("zh-CN", { month: "long", day: "numeric", weekday: "long" });
  const actions = data?.actions ?? [];
  const notes = data?.notes ?? [];

  return <>
    <section className={styles.head}>
      <div>
        <p className="eyebrow">TODAY</p>
        <h2>{actions.length > 0 ? `${actions.length} 件需要你处理` : "今天没有等你的事"}</h2>
        <p className={styles.copy}>{today} · 邮件更新、任务结果和物品提醒都会汇总到这里，不用一个个页面翻。</p>
      </div>
      <div className={styles.headActions}>
        <button className="ghost" onClick={() => void load()} disabled={loading}>
          <Icon name="refresh" size={14} /> 刷新
        </button>
        <button className="primary" onClick={() => onNavigate("chat")}>问一句</button>
      </div>
    </section>

    {error && <p className={styles.error}><Icon name="alert" size={15} /> {error}</p>}

    {actions.length > 0 && <section className={`workspace-card ${styles.panel}`}>
      <div className={styles.panelHead}>
        <h3>需要你处理</h3>
        <span>{actions.length}</span>
      </div>
      {actions.map((item, index) => <button key={`${item.kind}-${index}`} className={styles.row} onClick={() => onNavigate(item.target)}>
        <span className={`${styles.icon} ${styles.action}`}><Icon name={kindIcon[item.kind] || "alert"} size={16} /></span>
        <span className={styles.body}>
          <b>{item.title}</b>
          <small>{item.detail}</small>
        </span>
        <span className={styles.meta}>
          <small>{kindLabel[item.kind] || item.kind}</small>
          <small>{when(item.created_at)}</small>
        </span>
        <Icon name="chevron" size={15} />
      </button>)}
    </section>}

    {notes.length > 0 && <section className={`workspace-card ${styles.panel}`}>
      <div className={styles.panelHead}>
        <h3>最近变化</h3>
        <span>{notes.length}</span>
      </div>
      {notes.map((item, index) => <button key={`${item.kind}-n-${index}`} className={styles.row} onClick={() => onNavigate(item.target)}>
        <span className={styles.icon}><Icon name={kindIcon[item.kind] || "sparkles"} size={16} /></span>
        <span className={styles.body}>
          <b>{item.title}</b>
          <small>{item.detail}</small>
        </span>
        <span className={styles.meta}>
          <small>{kindLabel[item.kind] || item.kind}</small>
          <small>{when(item.created_at)}</small>
        </span>
        <Icon name="chevron" size={15} />
      </button>)}
    </section>}

    {data && data.count === 0 && <section className={styles.empty}>
      <Icon name="check" size={22} />
      <h3>没有待处理的事</h3>
      <p>可以让 Fei 做点什么：整理简历、记一件家里的东西，或者查一份岗位。</p>
      <div className={styles.emptyActions}>
        <button className="primary" onClick={() => onNavigate("chat")}>打开对话</button>
        <button className="ghost" onClick={() => onNavigate("items")}>记一件物品</button>
      </div>
    </section>}
  </>;
}
