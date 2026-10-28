"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { Icon } from "./Icon";
import styles from "./HouseholdWorkspace.module.css";

type Item = {
  id: string;
  name: string;
  quantity: number;
  unit: string | null;
  location_text: string;
  location_path: string[];
  note: string | null;
  status: string;
  updated_at: string | null;
};

type LocationRow = { path: string; items: number };

type ItemEvent = {
  id: string;
  action: string;
  from_path: string[] | null;
  to_path: string[] | null;
  qty_delta: number | null;
  source_text: string | null;
  created_at: string | null;
};

type Draft = {
  action: string;
  name: string | null;
  quantity: number;
  unit: string | null;
  location: string | null;
};

type Candidate = string | { id: string; label: string };

type IngestResult = {
  status: "applied" | "pending" | "answered" | "preview";
  applied: { summary: string; item: Item }[];
  answer: { summary: string; answer: Item[] }[];
  pending: { question: string; reason: string; candidates: Candidate[]; draft: Draft } | null;
  undo: string[];
  actions?: Draft[];
};

const actionLabels: Record<string, string> = {
  put: "放入",
  move: "移动",
  consume: "用掉",
  remove: "移出",
  adjust: "调整",
  undo: "撤销",
};

function request<T>(path: string, init?: RequestInit): Promise<T> {
  return api<T>(path, init);
}

export function HouseholdWorkspace() {
  const [items, setItems] = useState<Item[]>([]);
  const [locations, setLocations] = useState<LocationRow[]>([]);
  const [query, setQuery] = useState("");
  const [place, setPlace] = useState("");
  const [captureText, setCaptureText] = useState("");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [question, setQuestion] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [answer, setAnswer] = useState<Item[] | null>(null);
  const [preview, setPreview] = useState<Draft[] | null>(null);
  const [lastUndo, setLastUndo] = useState<string | null>(null);
  const [sourceText, setSourceText] = useState("");
  const [selected, setSelected] = useState<Item | null>(null);
  const [history, setHistory] = useState<ItemEvent[]>([]);
  const [moveTo, setMoveTo] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = useCallback(async (nextQuery = query, nextPlace = place) => {
    const params = new URLSearchParams();
    if (nextQuery.trim()) params.set("q", nextQuery.trim());
    if (nextPlace) params.set("location", nextPlace);
    const [rows, places] = await Promise.all([
      request<Item[]>(`/api/household/items?${params.toString()}`),
      request<LocationRow[]>("/api/household/locations"),
    ]);
    setItems(rows);
    setLocations(places);
  }, [query, place]);

  useEffect(() => {
    refresh().catch((err) => setError(String(err.message || err)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const grouped = useMemo(() => {
    const map = new Map<string, Item[]>();
    for (const item of items) {
      const room = item.location_path[0] || "未分类";
      map.set(room, [...(map.get(room) || []), item]);
    }
    return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0], "zh"));
  }, [items]);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const resetFeedback = () => {
    setNotice(null);
    setAnswer(null);
    setLastUndo(null);
    setQuestion(null);
    setCandidates([]);
    setPreview(null);
  };

  const ingest = () => run(async () => {
    const text = captureText.trim();
    if (!text) return;
    resetFeedback();
    const result = await request<IngestResult>("/api/household/ingest", {
      method: "POST",
      body: JSON.stringify({ text }),
    });

    if (result.status === "preview" && result.actions) {
      setPreview(result.actions);
      setSourceText(text);
      return;
    }

    if (result.status === "applied" && result.applied.length > 0) {
      setNotice(result.applied.map((row) => row.summary).join("；"));
      setLastUndo(result.undo[0] || null);
      setCaptureText("");
      setDraft(null);
      await refresh();
      return;
    }

    if (result.status === "answered") {
      const first = result.answer[0];
      setAnswer(first?.answer || []);
      setNotice(first?.summary || "没有记录");
      return;
    }

    if (result.pending) {
      setQuestion(result.pending.question);
      setCandidates(result.pending.candidates || []);
      setDraft(result.pending.draft);
      setSourceText(text);
    }
  });

  const updatePreview = (index: number, patch: Partial<Draft>) => {
    if (!preview) return;
    setPreview(preview.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  };

  const saveBatch = () => run(async () => {
    if (!preview) return;
    const items = preview
      .filter((row) => row.name && row.location)
      .map((row) => ({
        name: row.name,
        location: row.location,
        quantity: row.quantity || 1,
        unit: row.unit || undefined,
      }));
    if (items.length === 0) {
      setError("清单里还没有可保存的行");
      return;
    }
    const result = await request<{ count: number; pending: { question: string }[] }>("/api/household/batch", {
      method: "POST",
      body: JSON.stringify({ items, text: sourceText }),
    });
    setPreview(null);
    setCaptureText("");
    setSourceText("");
    setNotice(`已记下 ${result.count} 件${result.pending.length ? `，${result.pending.length} 行需要再看看` : ""}`);
    await refresh();
  });

  const undo = () => run(async () => {
    if (!lastUndo) return;
    await request<Item>(`/api/household/items/${lastUndo}/undo`, { method: "POST" });
    setNotice("已撤销");
    setLastUndo(null);
    await refresh();
  });

  const save = () => run(async () => {
    if (!draft?.name || !draft.location) {
      setError("还需要物品名和位置");
      return;
    }
    await request<Item>("/api/household/items", {
      method: "POST",
      body: JSON.stringify({
        name: draft.name,
        location: draft.location,
        quantity: draft.quantity || 1,
        unit: draft.unit || undefined,
        source_text: sourceText,
      }),
    });
    setDraft(null);
    setQuestion(null);
    setCaptureText("");
    setSourceText("");
    setNotice("已记下");
    await refresh();
  });

  const open = (item: Item) => run(async () => {
    setSelected(item);
    setMoveTo(item.location_text);
    setHistory(await request<ItemEvent[]>(`/api/household/items/${item.id}/history`));
  });

  const move = () => run(async () => {
    if (!selected) return;
    const updated = await request<Item>(`/api/household/items/${selected.id}/move`, {
      method: "PATCH",
      body: JSON.stringify({ location: moveTo }),
    });
    setSelected(updated);
    setHistory(await request<ItemEvent[]>(`/api/household/items/${selected.id}/history`));
    setNotice("位置已更新");
    await refresh();
  });

  const consume = (quantity: number) => run(async () => {
    if (!selected) return;
    const updated = await request<Item>(`/api/household/items/${selected.id}/consume`, {
      method: "POST",
      body: JSON.stringify({ quantity }),
    });
    setSelected(updated);
    setHistory(await request<ItemEvent[]>(`/api/household/items/${selected.id}/history`));
    setNotice(updated.status === "used_up" ? "已用完，移出清单" : "数量已更新");
    await refresh();
  });

  const search = (nextQuery: string, nextPlace: string) => run(async () => {
    setQuery(nextQuery);
    setPlace(nextPlace);
    await refresh(nextQuery, nextPlace);
  });

  return <div className="workspace-scroll">
    <section className={styles.head}>
      <div>
        <p className="eyebrow">HOUSEHOLD AGENT</p>
        <h2>物品清单</h2>
      </div>
      <span className={styles.count}>{items.length} 件在库</span>
    </section>

    <section className={`workspace-card ${styles.capture}`}>
      <div className={styles.captureRow}>
        <input
          value={captureText}
          onChange={(event) => setCaptureText(event.target.value)}
          onKeyDown={(event) => { if (event.key === "Enter") ingest(); }}
          placeholder="一句也行，整段清单也行：洗衣液放衣柜第二层"
          aria-label="用一句话或一整段清单记录物品"
        />
        <button className="primary" onClick={ingest} disabled={busy || !captureText.trim()}>
          <Icon name="sparkles" size={15} /> 记下
        </button>
      </div>

      {notice && <div className={styles.notice}>
        <Icon name="check" size={15} />
        <span>{notice}</span>
        {lastUndo && <button className={styles.linkButton} onClick={undo} disabled={busy}>撤销</button>}
      </div>}

      {preview && <div className={styles.preview}>
        <div className={styles.previewHead}>
          <strong>清单预览 · {preview.length} 行</strong>
          <span className={styles.hint}>每行都能改，确认后一起保存</span>
        </div>
        <div className={styles.previewRows}>
          {preview.map((row, index) => <div key={index} className={styles.previewRow}>
            <input value={row.name || ""} onChange={(event) => updatePreview(index, { name: event.target.value })} placeholder="物品" aria-label="物品" />
            <input type="number" value={row.quantity} onChange={(event) => updatePreview(index, { quantity: Number(event.target.value) })} aria-label="数量" />
            <input value={row.unit || ""} onChange={(event) => updatePreview(index, { unit: event.target.value })} placeholder="单位" aria-label="单位" />
            <input value={row.location || ""} onChange={(event) => updatePreview(index, { location: event.target.value })} placeholder="位置" aria-label="位置" />
            <button className="ghost" onClick={() => setPreview(preview.filter((_, i) => i !== index))} aria-label="删除这一行"><Icon name="close" size={14} /></button>
          </div>)}
        </div>
        <div className={styles.draftActions}>
          <button className="primary" onClick={saveBatch} disabled={busy}>全部记下</button>
          <button className="ghost" onClick={() => { setPreview(null); setCaptureText(""); }} disabled={busy}>取消</button>
        </div>
      </div>}

      {answer && answer.length > 0 && <div className={styles.answerList}>
        {answer.map((row) => <div key={row.id} className={styles.answerRow}>
          <b>{row.name}</b>
          <span>{row.location_text}</span>
          <small>{row.quantity}{row.unit || ""}</small>
        </div>)}
      </div>}

      {draft && <div className={styles.draft}>
        <div className={styles.draftHead}>
          <strong>{question || actionLabels[draft.action] || "记录"}</strong>
          <span className={styles.confidence}>确认后保存</span>
        </div>
        {candidates.length > 0 && <div className={styles.chips}>
          {candidates.map((candidate) => {
            const label = typeof candidate === "string" ? candidate : candidate.label;
            return <button key={label} className={styles.chip}
              onClick={() => {
                if (typeof candidate === "string") setDraft({ ...draft, location: candidate });
              }}>{label}</button>;
          })}
        </div>}
        <div className={styles.fields}>
          <label><span>物品</span>
            <input value={draft.name || ""} onChange={(event) => setDraft({ ...draft, name: event.target.value })} />
          </label>
          <label><span>数量</span>
            <input type="number" value={draft.quantity} onChange={(event) => setDraft({ ...draft, quantity: Number(event.target.value) })} />
          </label>
          <label><span>单位</span>
            <input value={draft.unit || ""} onChange={(event) => setDraft({ ...draft, unit: event.target.value })} />
          </label>
          <label className={styles.wide}><span>位置（用 / 分层）</span>
            <input value={draft.location || ""} onChange={(event) => setDraft({ ...draft, location: event.target.value })} />
          </label>
        </div>
        <div className={styles.draftActions}>
          <button className="primary" onClick={save} disabled={busy}>保存</button>
          <button className="ghost" onClick={() => { setDraft(null); setQuestion(null); setCandidates([]); }} disabled={busy}>取消</button>
          <span className={styles.hint}>只有拿不准时才会出现这张卡。</span>
        </div>
      </div>}
    </section>

    {error && <p className={styles.error}><Icon name="alert" size={15} /> {error}</p>}

    <div className={styles.layout}>
      <section className="workspace-card">
        <div className={styles.toolbar}>
          <label className={styles.search}>
            <Icon name="search" size={15} />
            <input value={query} onChange={(event) => search(event.target.value, place)} placeholder="搜索物品" />
          </label>
          <select value={place} onChange={(event) => search(query, event.target.value)} aria-label="按位置筛选">
            <option value="">全部位置</option>
            {locations.map((row) => <option key={row.path} value={row.path}>{row.path}（{row.items}）</option>)}
          </select>
        </div>

        {items.length === 0
          ? <p className={styles.empty}>还没有记录。说一句「洗衣液放衣柜第二层」试试。</p>
          : <div className={styles.table}>
              <div className={styles.tableHead}><span>物品</span><span>数量</span><span>位置</span><span>更新</span></div>
              {grouped.map(([room, rows]) => <div key={room} className={styles.group}>
                <p className={styles.room}>{room}</p>
                {rows.map((item) => <button key={item.id} className={styles.row} onClick={() => open(item)}>
                  <span className={styles.name}>{item.name}</span>
                  <span>{item.quantity}{item.unit || ""}</span>
                  <span className={styles.place}>{item.location_text}</span>
                  <span className={styles.time}>{item.updated_at ? item.updated_at.slice(5, 16).replace("T", " ") : ""}</span>
                </button>)}
              </div>)}
            </div>}
      </section>

      <aside className={`workspace-card ${styles.detail}`}>
        {!selected
          ? <p className={styles.empty}>点一行查看历史、改位置或用掉一件。</p>
          : <>
              <div className={styles.detailHead}>
                <div><p className="eyebrow">ITEM</p><h3>{selected.name}</h3></div>
                <button className="ghost" onClick={() => setSelected(null)} aria-label="关闭详情"><Icon name="close" size={15} /></button>
              </div>
              <p className={styles.location}>{selected.location_path.map((part, index) =>
                <span key={`${part}-${index}`}>{index > 0 && <i>›</i>}{part}</span>)}</p>
              <p className={styles.stock}>{selected.quantity}{selected.unit || ""} · {selected.status === "used_up" ? "已用完" : "在库"}</p>

              <div className={styles.moveRow}>
                <input value={moveTo} onChange={(event) => setMoveTo(event.target.value)} aria-label="新位置" />
                <button className="ghost" onClick={move} disabled={busy || moveTo === selected.location_text}>移动</button>
              </div>
              <button className="primary" onClick={() => consume(1)} disabled={busy || selected.quantity <= 0}>用掉 1{selected.unit || ""}</button>

              <h4 className={styles.historyTitle}>历史</h4>
              <ul className={styles.history}>
                {history.map((event) => <li key={event.id}>
                  <span className={styles.action}>{actionLabels[event.action] || event.action}</span>
                  <span>{event.created_at ? event.created_at.slice(0, 16).replace("T", " ") : ""}</span>
                </li>)}
              </ul>
            </>}
      </aside>
    </div>
  </div>;
}
