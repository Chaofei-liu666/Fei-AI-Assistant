"use client";

import { FormEvent, useEffect, useState, useSyncExternalStore, type ReactNode } from "react";
import { api } from "@/lib/api";
import { DEMO_SKIN, skin } from "@/lib/skin";

type Provider = { slot: string; provider: string; base_url?: string; model?: string; config: Record<string, unknown>; configured: boolean; secret_last_four?: string };

export function SettingsPanel() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [notice, setNotice] = useState("");
  const [orch, setOrch] = useState<{ prompt: string; default_prompt: string; customized: boolean } | null>(null);
  const skinCfg = useSyncExternalStore(skin.subscribe, skin.snapshot, skin.snapshot);
  const refresh = () => api<Provider[]>("/api/settings/providers").then(setProviders).catch((e) => setNotice(e.message));
  useEffect(() => { void refresh(); }, []);
  useEffect(() => { api<{ prompt: string; default_prompt: string; customized: boolean }>("/api/agents/orchestrator/prompt").then(setOrch).catch(() => {}); }, []);
  const pickSkinFile = (file?: File) => {
    if (!file) return;
    const isVideo = file.type.startsWith("video");
    const limit = isVideo ? 4.5 * 1024 * 1024 : 2.5 * 1024 * 1024;
    if (file.size > limit) {
      setNotice(isVideo ? "视频请小于 4.5MB（浏览器 localStorage 限制）" : "图片请小于 2.5MB");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => skin.set({
      kind: isVideo ? "video" : "image",
      src: String(reader.result),
      opacity: skinCfg.opacity,
      blur: skinCfg.blur,
    });
    reader.readAsDataURL(file);
  };

  const saveOrch = async () => {
    if (!orch) return;
    try {
      const data = await api<{ prompt: string; customized: boolean }>("/api/agents/orchestrator/prompt", { method: "PUT", body: JSON.stringify({ prompt: orch.prompt }) });
      setOrch({ ...orch, prompt: data.prompt, customized: data.customized });
      setNotice("主 Agent 提示词已保存");
    } catch (error) { setNotice(error instanceof Error ? error.message : "保存失败"); }
  };
  const resetOrch = async () => {
    try {
      const data = await api<{ prompt: string; customized: boolean }>("/api/agents/orchestrator/prompt", { method: "DELETE" });
      setOrch({ ...(orch as { default_prompt: string }), prompt: data.prompt, customized: data.customized });
      setNotice("已恢复默认提示词");
    } catch (error) { setNotice(error instanceof Error ? error.message : "重置失败"); }
  };
  const current = (slot: string) => providers.find((p) => p.slot === slot);
  const save = async (event: FormEvent<HTMLFormElement>, slot: string, provider: string) => {
    event.preventDefault(); const values = Object.fromEntries(new FormData(event.currentTarget));
    const config: Record<string, unknown> = {}; const secrets: Record<string, string> = {};
    for (const key of ["username","host","port","dashscope_workspace_id","dashscope_region_domain","oss_access_key_id","oss_endpoint","oss_bucket"]) if (values[key]) config[key] = values[key];
    if (values.oss_secret) secrets.oss_secret = String(values.oss_secret);
    const payload = { slot, provider: String(values.provider || provider), base_url: values.base_url || null, model: values.model || null, secret: values.secret || null, secrets, config };
    try { await api(`/api/settings/providers/${slot}`, { method: "PUT", body: JSON.stringify(payload) }); setNotice("配置已保存到系统凭据库"); refresh(); } catch (error) { setNotice(error instanceof Error ? error.message : "保存失败"); }
  };
  return <div className="workspace-scroll settings"><div className="workspace-heading"><div><h2>设置</h2></div></div>{notice && <div className="notice">{notice}</div>}
    <section className="workspace-card settings-form">
      <div><h3>Skin</h3><span className={`status-pill ${skinCfg.kind !== "none" ? "ready" : ""}`}>{skinCfg.kind === "none" ? "未启用" : skinCfg.kind}</span></div>
      <div className="skin-preview">
        {skinCfg.src
          ? skinCfg.kind === "video"
            ? <video src={skinCfg.src} muted loop autoPlay playsInline />
            : <img src={skinCfg.src} alt="" />
          : <p style={{ margin: 0, padding: 12, color: "var(--faint)", fontSize: 12 }}>未选择背景</p>}
      </div>
      <div className="skin-row">
        <input type="file" accept="image/*,video/*" onChange={(event) => pickSkinFile(event.target.files?.[0])} />
        <button type="button" onClick={() => skin.set({ kind: "image", src: DEMO_SKIN, opacity: skinCfg.opacity, blur: skinCfg.blur })}>使用示例</button>
        <label>可见度<input type="range" min={0.2} max={0.95} step={0.01} value={skinCfg.opacity} onChange={(event) => skin.set({ ...skinCfg, opacity: Number(event.target.value) })} /></label>
        <label>模糊<input type="range" min={0} max={40} step={1} value={skinCfg.blur} onChange={(event) => skin.set({ ...skinCfg, blur: Number(event.target.value) })} /></label>
        <button type="button" onClick={() => skin.clear()}>关闭皮肤</button>
      </div>
    </section>
    {orch && <section className="workspace-card settings-form">
      <div><h3>Orchestrator Prompt</h3><span className={`status-pill ${orch.customized ? "ready" : ""}`}>{orch.customized ? "自定义" : "默认"}</span></div>
      <textarea className="prompt-editor" rows={8} value={orch.prompt} onChange={(event) => setOrch({ ...orch, prompt: event.target.value })} />
      <div className="record-actions"><button className="primary" type="button" onClick={() => void saveOrch()}>保存提示词</button>{orch.customized && <button type="button" onClick={() => void resetOrch()}>恢复默认</button>}</div>
    </section>}
    <ProviderForm title="全局文本模型" slot="text" provider={current("text")?.provider || "deepseek"} saved={current("text")} onSubmit={save}>
      <select name="provider" defaultValue={current("text")?.provider || "deepseek"}><option value="deepseek">DeepSeek 预设</option><option value="openai_compatible">自定义 OpenAI-compatible</option></select><input name="base_url" placeholder="Base URL（DeepSeek 可留空）" defaultValue={current("text")?.base_url} /><input name="model" placeholder="模型名，例如 deepseek-chat" defaultValue={current("text")?.model} required /><input name="secret" type="password" placeholder={current("text")?.configured ? `API Key 已保存 ····${current("text")?.secret_last_four}` : "API Key"} />
    </ProviderForm>
    <ProviderForm title="阿里云 Paraformer" slot="speech" provider="aliyun_paraformer" saved={current("speech")} onSubmit={save}>
      <input name="model" defaultValue={current("speech")?.model || "paraformer-v2"} /><input name="secret" type="password" placeholder={current("speech")?.configured ? `DashScope Key 已保存 ····${current("speech")?.secret_last_four}` : "DashScope API Key"} /><input name="dashscope_workspace_id" placeholder="DashScope Workspace ID" defaultValue={String(current("speech")?.config.dashscope_workspace_id ?? "")} /><input name="dashscope_region_domain" placeholder="地域域名" defaultValue={String(current("speech")?.config.dashscope_region_domain ?? "cn-beijing.maas.aliyuncs.com")} /><input name="oss_access_key_id" placeholder="OSS AccessKey ID" defaultValue={String(current("speech")?.config.oss_access_key_id ?? "")} /><input name="oss_secret" type="password" placeholder="OSS AccessKey Secret（留空则不变）" /><input name="oss_endpoint" placeholder="OSS Endpoint" defaultValue={String(current("speech")?.config.oss_endpoint ?? "")} /><input name="oss_bucket" placeholder="私有 OSS Bucket" defaultValue={String(current("speech")?.config.oss_bucket ?? "")} />
    </ProviderForm>
    <ProviderForm title="163 邮箱（只读）" slot="email" provider="email_163" saved={current("email")} onSubmit={save}>
      <input name="username" type="email" placeholder="邮箱地址" defaultValue={String(current("email")?.config.username ?? "")} required /><input name="secret" type="password" placeholder={current("email")?.configured ? `授权码已保存 ····${current("email")?.secret_last_four}` : "客户端授权码"} /><input name="host" defaultValue={String(current("email")?.config.host ?? "imap.163.com")} /><input name="port" defaultValue={String(current("email")?.config.port ?? "993")} />
    </ProviderForm>
    <section className="workspace-card"><h3>环境变量管理</h3><p>PostgreSQL 与 MinIO 连接信息只从主机环境变量读取，不通过浏览器保存或展示。</p></section>
  </div>;
}

function ProviderForm({ title, slot, provider, saved, onSubmit, children }: { title: string; slot: string; provider: string; saved?: Provider; onSubmit: (event: FormEvent<HTMLFormElement>, slot: string, provider: string) => void; children: ReactNode }) {
  return <form className="workspace-card settings-form" onSubmit={(e) => onSubmit(e, slot, provider)}><div><h3>{title}</h3><span className={`status-pill ${saved?.configured ? "ready" : ""}`}>{saved?.configured ? "已配置" : "未配置"}</span></div><div className="form-grid">{children}</div><div className="record-actions"><button className="primary" type="submit">保存配置</button>{saved?.configured && <button type="button" onClick={() => fetch(`${process.env.NEXT_PUBLIC_FEI_API_URL ?? "http://127.0.0.1:8000"}/api/settings/providers/${slot}/test`, { method: "POST" }).then(async r => { if (!r.ok) throw new Error((await r.json()).detail); return r.json(); }).then(result => alert(`能力测试结果：${JSON.stringify(result)}`)).catch(error => alert(error.message))}>连接与能力测试</button>}</div></form>;
}
