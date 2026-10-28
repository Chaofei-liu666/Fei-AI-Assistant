"use client";

import { useEffect, useMemo, useState } from "react";
import { AuiIf, ComposerPrimitive, MessagePrimitive, ThreadPrimitive, useAuiState } from "@assistant-ui/react";
import { api } from "@/lib/api";
import { threads } from "@/lib/threads";
import { Icon, type IconName } from "./Icon";

const jobCapabilities = [
  ["target", "查询岗位", "读取 2027 校招岗位和要求—证据结论", "列出目前最值得关注的 2027 校招岗位，并解释证据和核心缺口"],
  ["columns", "查看投递", "读取阶段、官网证据和事件时间线", "总结我当前的投递进度，并指出下一步需要跟进的事项"],
  ["mail", "处理邮件", "解释只读邮件建议并引导人工确认", "查看待确认的招聘邮件建议，并告诉我每封邮件为什么这样分类"],
] as [IconName, string, string, string][];

const generalSuggestions = [
  ["briefcase", "规划求职任务", "把岗位、投递和面试安排成今天可执行的清单", "根据我目前的求职数据，帮我规划今天最应该完成的任务"],
  ["file", "整理复杂信息", "提炼重点、风险和下一步行动", "我会提供一段复杂信息，请按重点、风险和下一步行动帮我整理"],
  ["sparkles", "调用合适模块", "先识别意图，再交给对应 Specialist", "告诉我 Fei 当前可以协助哪些任务，以及会如何选择模块"],
] as [IconName, string, string, string][];


type DigestItem = { kind: string; title: string; detail: string; target: string };

function TodayDigest({ onNavigate }: { onNavigate?: (target: string) => void }) {
  const [data, setData] = useState<{ count: number; actions: DigestItem[]; notes: DigestItem[] } | null>(null);

  useEffect(() => {
    let alive = true;
    api<{ count: number; actions: DigestItem[]; notes: DigestItem[] }>("/api/inbox")
      .then((payload) => { if (alive) setData(payload); })
      .catch(() => {});
    return () => { alive = false; };
  }, []);

  if (!data || data.count === 0) return null;

  if (data.actions.length === 0) {
    const names = data.notes.slice(0, 3).map((item) => item.title.replace(/\s*快用完了$/, "")).join("、");
    return <button className="digest-strip" onClick={() => onNavigate?.("today")}>
      <span className="digest-dot" />
      <span>今天有 {data.count} 件小事{names ? ` · ${names}` : ""}</span>
      <span className="digest-link">查看 ›</span>
    </button>;
  }

  return <div className="digest">
    <div className="digest-head">
      <span>需要你处理</span>
      <span className="digest-count">{data.actions.length}</span>
      <button onClick={() => onNavigate?.("today")}>全部 ›</button>
    </div>
    {data.actions.slice(0, 2).map((item, index) => <button key={`${item.kind}-${index}`} className="digest-row" onClick={() => onNavigate?.(item.target)}>
      <span className={`digest-dot ${item.kind}`} />
      <span className="digest-body"><b>{item.title}</b><small>{item.detail}</small></span>
    </button>)}
    {data.notes.length > 0 && <p className="digest-foot">另有 {data.notes.length} 条变化，可在“今天”查看</p>}
  </div>;
}

function ChatComposer({ isJob }: { isJob: boolean }) {
  return <ComposerPrimitive.Root className="composer">
    <ComposerPrimitive.Input
      className="composer-input"
      placeholder={isJob ? "询问岗位分析、招聘邮件或面试复盘……" : "告诉 Fei 你要处理什么……"}
      rows={1}
      title="Enter 发送 · Shift + Enter 换行"
    />
    <div className="composer-bar">
      <span className="permission-chip"><Icon name="lock" size={12} /> 写入需确认</span>
      <div className="composer-right">
        <ComposerControls />
        <AuiIf condition={(state) => !state.thread.isRunning}><ComposerPrimitive.Send className="send-button">↑</ComposerPrimitive.Send></AuiIf>
        <AuiIf condition={(state) => state.thread.isRunning}><ComposerPrimitive.Cancel className="send-button stop">■</ComposerPrimitive.Cancel></AuiIf>
      </div>
    </div>
  </ComposerPrimitive.Root>;
}

export function ChatThread({ module, onNavigate }: { module: "general" | "job_search"; onNavigate?: (target: string) => void }) {
  const isJob = module === "job_search";
  const threadMessages = useAuiState((state) => state.thread.messages);

  useEffect(() => {
    const active = threads.snapshot().active;
    if (!active) return;
    const first = (threadMessages ?? []).find((message) => message.role === "user");
    if (!first) return;
    const text = first.content.map((part) => (part.type === "text" ? part.text : "")).join(" ").trim();
    if (text) threads.rename(active, text);
  }, [threadMessages]);

  return <ThreadPrimitive.Root className="thread-root">
    <ThreadPrimitive.Viewport className="thread-viewport">
      <AuiIf condition={(state) => state.thread.isEmpty}>
        <section className="welcome">
          <div className="welcome-logo">F</div><p className="eyebrow">FEI ASSISTANT</p>
          <h2>{isJob ? "把求职过程变成可追溯的工作流" : "今天想先处理什么？"}</h2>
          <p className="welcome-copy">{isJob ? "这里负责求职对话；岗位、投递、邮件和面试数据请在工作区管理。" : "Fei 会处理通用请求，并在任务明确涉及求职时自动调用求职模块。"}</p>
          <TodayDigest onNavigate={onNavigate} />
          <div className="suggest-row">{(isJob ? jobCapabilities : generalSuggestions).map(([icon, title, text, prompt]) => <ThreadPrimitive.Suggestion className="suggest-chip" prompt={prompt} key={title} title={text}><Icon name={icon} size={14} /><span>{title}</span></ThreadPrimitive.Suggestion>)}</div>
          <div className="welcome-composer">
            <ChatComposer isJob={isJob} />
            <ComposerStats />
            <p className="disclaimer">模型只提供分析建议；状态变更和外部操作均需用户确认。</p>
          </div>
        </section>
      </AuiIf>
      <div className="messages"><ThreadPrimitive.Messages>{({ message }) => message.role === "user" ? <UserMessage /> : <AssistantMessage module={module} />}</ThreadPrimitive.Messages></div>
      <AuiIf condition={(state) => !state.thread.isEmpty}>
        <ThreadPrimitive.ViewportFooter className="composer-footer">
          <ChatComposer isJob={isJob} />
          <ComposerStats />
          <p className="disclaimer">模型只提供分析建议；状态变更和外部操作均需用户确认。</p>
        </ThreadPrimitive.ViewportFooter>
      </AuiIf>
    </ThreadPrimitive.Viewport>
  </ThreadPrimitive.Root>;
}

function UserMessage() { return <MessagePrimitive.Root className="message-row user-row"><div className="user-message"><MessagePrimitive.Parts /></div></MessagePrimitive.Root>; }
function AssistantMessage({ module }: { module: string }) { return <MessagePrimitive.Root className="message-row assistant-row"><div className="assistant-avatar">F</div><div className="assistant-content"><div className="message-author">Fei 智能助手{module === "job_search" ? " · 求职模块" : ""}</div><div className="assistant-message"><MessagePrimitive.Parts /></div></div></MessagePrimitive.Root>; }

type MessageStats = {
  role: "user" | "assistant" | "system";
  metadata?: {
    timing?: { toolCallCount?: number; tokenCount?: number; tokensPerSecond?: number };
    steps?: { usage?: { inputTokens?: number; outputTokens?: number } }[];
  };
};

type ModelInfo = { id: string; name: string; efforts: string[]; default_effort: string; context_window?: number };
type ProviderRow = {
  slot: string;
  provider: string;
  base_url: string | null;
  model: string | null;
  config: Record<string, unknown>;
};

const FALLBACK_CONTEXT = 128_000;
let contextPromise: Promise<number> | null = null;

function resetContextCache() {
  contextPromise = null;
}

function loadContextWindow(): Promise<number> {
  if (!contextPromise) {
    contextPromise = Promise.all([
      api<ProviderRow[]>("/api/settings/providers").catch(() => [] as ProviderRow[]),
      api<ModelInfo[]>("/api/settings/models").catch(() => [] as ModelInfo[]),
    ])
      .then(([rows, list]) => {
        const text = (rows as ProviderRow[]).find((row) => row.slot === "text");
        const info = (list as ModelInfo[]).find((item) => item.id === text?.model);
        return info?.context_window || FALLBACK_CONTEXT;
      })
      .catch(() => FALLBACK_CONTEXT);
  }
  return contextPromise;
}

function formatTokens(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}k`;
  return `${value}`;
}

function ComposerStats() {
  const messages = useAuiState((state) => state.thread.messages) as unknown as MessageStats[];
  const [contextWindow, setContextWindow] = useState(FALLBACK_CONTEXT);

  useEffect(() => {
    const update = () => { void loadContextWindow().then(setContextWindow); };
    update();
    window.addEventListener("fei:model-changed", update);
    return () => window.removeEventListener("fei:model-changed", update);
  }, []);

  const stats = useMemo(() => {
    let turns = 0;
    let steps = 0;
    let tokens = 0;
    let tps: number | undefined;
    for (const message of messages ?? []) {
      if (message.role === "user") turns += 1;
      if (message.role !== "assistant") continue;
      const timing = message.metadata?.timing;
      if (timing?.toolCallCount) steps += timing.toolCallCount;
      if (typeof timing?.tokensPerSecond === "number") tps = timing.tokensPerSecond;
      const usage = (message.metadata?.steps ?? []).reduce(
        (sum, step) => sum + (step.usage?.inputTokens ?? 0) + (step.usage?.outputTokens ?? 0), 0);
      tokens += usage || timing?.tokenCount || 0;
    }
    return { turns, steps, tokens, tps };
  }, [messages]);

  const contextPct = stats.tokens > 0 ? Math.min(100, Math.round((stats.tokens / contextWindow) * 100)) : 0;

  if (stats.turns === 0) return null;

  const rate = typeof stats.tps === "number" && stats.tps > 0 ? `${stats.tps.toFixed(0)} tok/s` : "—";

  return <div className="composer-meta">
    <span className="cm-group"><b>{stats.turns}</b> 轮 <i>·</i> <b>{stats.steps}</b> 步 <i>·</i> {rate}</span>
    <span className="cm-sep" />
    <span className="cm-group">{formatTokens(stats.tokens)} tok <i>·</i> 缓存 <b title="provider 暂未返回缓存命中">—</b></span>
    <span className="cm-sep" />
    <span className="cm-group" title={`上下文窗口 ${contextWindow.toLocaleString()} tokens`}>上下文 <b>{contextPct}%</b></span>
  </div>;
}

const effortLabels: Record<string, string> = { low: "快速", high: "标准", max: "深度" };

function ComposerControls() {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [provider, setProvider] = useState<ProviderRow | null>(null);
  const [model, setModel] = useState("");
  const [effort, setEffort] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let alive = true;
    Promise.all([
      api<ProviderRow[]>("/api/settings/providers").catch(() => [] as ProviderRow[]),
      api<ModelInfo[]>("/api/settings/models").catch(() => [] as ModelInfo[]),
    ])
      .then(([rows, list]) => {
        if (!alive) return;
        const text = (rows as ProviderRow[]).find((row) => row.slot === "text");
        if (!text) return;
        const available = Array.isArray(list) ? (list as ModelInfo[]) : [];
        setProvider(text);
        setModels(available);
        setModel(text.model || "");
        const saved = typeof text.config?.effort === "string" ? text.config.effort : "";
        const info = available.find((item) => item.id === text.model);
        setEffort(saved || info?.default_effort || "high");
      })
      .catch(() => {});
    return () => { alive = false; };
  }, []);

  const current = models.find((item) => item.id === model) || models[0];

  const persist = async (nextModel: string, nextEffort: string) => {
    if (!provider) return;
    setSaving(true);
    try {
      const saved = await api<ProviderRow>("/api/settings/providers/text", {
        method: "PUT",
        body: JSON.stringify({
          slot: "text",
          provider: provider.provider,
          base_url: provider.base_url,
          model: nextModel,
          config: { ...(provider.config || {}), effort: nextEffort },
        }),
      });
      setProvider({ ...provider, model: saved.model, config: saved.config || {} });
      resetContextCache();
      window.dispatchEvent(new Event("fei:model-changed"));
    } finally {
      setSaving(false);
    }
  };

  if (models.length === 0) return null;

  return <div className="composer-controls">
    <select
      className="composer-select"
      value={model}
      disabled={saving}
      aria-label="模型"
      onChange={(event) => {
        const next = event.target.value;
        const info = models.find((item) => item.id === next);
        const nextEffort = info?.efforts.includes(effort) ? effort : (info?.default_effort || "high");
        setModel(next);
        setEffort(nextEffort);
        void persist(next, nextEffort);
      }}
    >
      {model && !models.some((item) => item.id === model) && <option value={model}>{model}</option>}
      {models.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
    </select>
    {current && current.efforts.length > 0 && <select
      className="composer-select"
      value={effort}
      disabled={saving}
      aria-label="推理等级"
      onChange={(event) => {
        const next = event.target.value;
        setEffort(next);
        void persist(model, next);
      }}
    >
      {current.efforts.map((level) => <option key={level} value={level}>推理 {effortLabels[level] || level}</option>)}
    </select>}
  </div>;
}
