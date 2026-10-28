"use client";

import { useCallback, useEffect, useState } from "react";
import { Icon } from "./Icon";
import styles from "./RunsWorkspace.module.css";

type RunRow = { run_id: string; steps: number; last_at: string | null };
type Step = {
  id: string;
  seq: number;
  kind: string;
  actor: string | null;
  title: string;
  status: string;
  summary: string | null;
  detail: Record<string, unknown>;
  started_at: string | null;
  ended_at: string | null;
  error: string | null;
};

const kindLabels: Record<string, string> = {
  plan: "计划",
  delegate: "委派",
  tool: "工具",
  result: "结果",
  approval: "待确认",
  error: "失败",
  note: "记录",
};

const kindTone: Record<string, string> = {
  plan: "tonePlan",
  delegate: "toneDelegate",
  tool: "toneTool",
  result: "toneResult",
  approval: "toneApproval",
  error: "toneError",
  note: "toneNote",
};

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(response.statusText);
  return response.json() as Promise<T>;
}

function time(value: string | null): string {
  return value ? value.slice(5, 16).replace("T", " ") : "";
}

export function RunsWorkspace() {
  const [runs, setRuns] = useState<RunRow[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setRuns(await getJson<RunRow[]>("/api/runs?limit=30"));
  }, []);

  useEffect(() => {
    load().catch((err) => setError(String(err.message || err)));
  }, [load]);

  const open = async (runId: string) => {
    setActive(runId);
    setError(null);
    try {
      const payload = await getJson<{ steps: Step[] }>(`/api/runs/${runId}/steps`);
      setSteps(payload.steps);
    } catch (err) {
      setSteps([]);
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  return <>
    <section className={styles.head}>
      <div>
        <p className="eyebrow">RUNS</p>
        <h2>运行记录</h2>
        <p className={styles.copy}>每一次对话或后台任务都是一次运行。这里按顺序记录计划、委派、工具调用和结果；默认只看到摘要，点开才看细节。</p>
      </div>
      <span className={styles.count}>{runs.length} 次运行</span>
    </section>

    {error && <p className={styles.error}><Icon name="alert" size={15} /> {error}</p>}

    <div className={styles.layout}>
      <section className="workspace-card">
        <div className={styles.listHead}><span>运行</span><span>步骤</span><span>时间</span></div>
        {runs.length === 0 && <p className={styles.empty}>还没有运行记录。去主对话里问一句，或触发一次后台任务。</p>}
        {runs.map((run) => <button
          key={run.run_id}
          className={`${styles.runRow} ${active === run.run_id ? styles.active : ""}`}
          onClick={() => open(run.run_id)}
        >
          <span className={styles.runId}>{run.run_id.slice(0, 12)}</span>
          <span>{run.steps}</span>
          <span className={styles.time}>{time(run.last_at)}</span>
        </button>)}
      </section>

      <section className={`workspace-card ${styles.detail}`}>
        {!active
          ? <p className={styles.empty}>选一次运行，看它的执行过程。</p>
          : <>
              <div className={styles.detailHead}>
                <div><p className="eyebrow">TIMELINE</p><h3 className={styles.mono}>{active.slice(0, 12)}</h3></div>
                <button className="ghost" onClick={() => { setActive(null); setSteps([]); }} aria-label="关闭"><Icon name="close" size={15} /></button>
              </div>
              <ol className={styles.timeline}>
                {steps.map((step) => <li key={step.id} className={styles.step}>
                  <span className={`${styles.dot} ${styles[kindTone[step.kind] || "note"]}`} />
                  <div className={styles.stepBody}>
                    <div className={styles.stepTop}>
                      <span className={styles.kind}>{kindLabels[step.kind] || step.kind}</span>
                      {step.actor && <span className={styles.actor}>{step.actor}</span>}
                      <span className={styles.stepTime}>{time(step.ended_at || step.started_at)}</span>
                    </div>
                    <p className={styles.title}>{step.title}</p>
                    {step.summary && <p className={styles.summary}>{step.summary}</p>}
                    {step.error && <p className={styles.errorLine}>{step.error}</p>}
                    {Object.keys(step.detail || {}).length > 0 && <details className={styles.detailBox}>
                      <summary>细节</summary>
                      <pre>{JSON.stringify(step.detail, null, 2)}</pre>
                    </details>}
                  </div>
                </li>)}
              </ol>
            </>}
      </section>
    </div>
  </>;
}
